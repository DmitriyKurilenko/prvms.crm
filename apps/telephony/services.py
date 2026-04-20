from __future__ import annotations

import xml.sax.saxutils as _sax
from dataclasses import dataclass

from django_tenants.utils import schema_context, tenant_context

from apps.tenants.models import Domain, Tenant
from .models import CallQueue, IVRMenu, PhoneExtension, SIPTrunk

XML_NOT_FOUND = (
    '<?xml version="1.0" encoding="UTF-8" standalone="no"?>'
    '<document type="freeswitch/xml">'
    '<section name="result"><result status="not found"/></section>'
    '</document>'
)


@dataclass
class DialplanDecision:
    action: str
    destination: str
    details: dict


# ---------------------------------------------------------------------------
# Tenant resolution
# ---------------------------------------------------------------------------

def resolve_tenant_for_telephony(payload: dict) -> Tenant | None:
    # FreeSWITCH sends channel vars prefixed with "variable_"
    tenant_slug = (
        payload.get('tenant_slug')
        or payload.get('variable_tenant_slug')
    )
    tenant_id = payload.get('tenant_id')
    # FS sends domain_name for directory lookups
    domain = payload.get('domain') or payload.get('domain_name') or payload.get('key_value')

    with schema_context('public'):
        if tenant_id:
            tenant = Tenant.objects.filter(id=tenant_id, is_active=True).first()
            if tenant:
                return tenant
        if tenant_slug:
            tenant = Tenant.objects.filter(slug=tenant_slug, is_active=True).first()
            if tenant:
                return tenant
        if domain:
            # Try per-tenant SIP domain first (e.g. org-crm.sip.localhost)
            tenant = Tenant.objects.filter(sip_domain=domain, is_active=True).first()
            if tenant:
                return tenant
            domain_row = (
                Domain.objects.select_related('tenant')
                .filter(domain=domain, tenant__is_active=True)
                .first()
            )
            if domain_row:
                return domain_row.tenant
    return None


# ---------------------------------------------------------------------------
# Dialplan decision
# ---------------------------------------------------------------------------

def build_dialplan_decision(tenant: Tenant, payload: dict) -> DialplanDecision:
    # Normalise FreeSWITCH field names alongside our own convention
    called = str(
        payload.get('destination')
        or payload.get('called_number')
        or payload.get('Caller-Destination-Number')
        or payload.get('destination_number')
        or ''
    ).strip()
    caller = str(
        payload.get('caller_number')
        or payload.get('Caller-Caller-ID-Number')
        or ''
    ).strip()

    with tenant_context(tenant):
        # 1. DID routing: inbound PSTN call to a number registered in a trunk's inbound_numbers.
        #    Takes priority so PSTN DIDs are never mistaken for internal extensions.
        if called:
            did_trunk = _trunk_for_did(called)
            if did_trunk:
                ivr = IVRMenu.objects.filter(is_active=True).order_by('id').first()
                if ivr:
                    return DialplanDecision(
                        action='ivr',
                        destination=ivr.name,
                        details={
                            'type': 'ivr',
                            'ivr_id': ivr.id,
                            'timeout': ivr.timeout,
                            'options': ivr.options,
                            'greeting_tts': ivr.greeting_tts,
                            'greeting_audio_url': ivr.greeting_audio.url if ivr.greeting_audio else '',
                        },
                    )
                queue = CallQueue.objects.filter(is_active=True).order_by('id').first()
                if queue:
                    return DialplanDecision(
                        action='queue',
                        destination=queue.name,
                        details={'type': 'queue', 'queue_id': queue.id, 'strategy': queue.strategy},
                    )

        # 2. Extension routing (internal / WebRTC calls)
        if called:
            extension = PhoneExtension.objects.filter(extension=called, is_active=True).first()
            if extension:
                return DialplanDecision(
                    action='bridge',
                    destination=f'user/{extension.extension}',
                    details={'type': 'extension', 'extension': extension.extension, 'caller': caller},
                )

        # 3. Queue by name
        queue = _queue_for_number(called)
        if queue:
            return DialplanDecision(
                action='queue',
                destination=queue.name,
                details={'type': 'queue', 'queue_id': queue.id, 'strategy': queue.strategy},
            )

        # 4. Default IVR
        ivr = IVRMenu.objects.filter(is_active=True).order_by('id').first()
        if ivr:
            return DialplanDecision(
                action='ivr',
                destination=ivr.name,
                details={
                    'type': 'ivr',
                    'ivr_id': ivr.id,
                    'timeout': ivr.timeout,
                    'options': ivr.options,
                    'greeting_tts': ivr.greeting_tts,
                    'greeting_audio_url': ivr.greeting_audio.url if ivr.greeting_audio else '',
                },
            )

        # 5. Fallback to first available extension
        fallback = PhoneExtension.objects.filter(is_active=True).order_by('extension').first()
        if fallback:
            return DialplanDecision(
                action='bridge',
                destination=f'user/{fallback.extension}',
                details={'type': 'fallback_extension', 'extension': fallback.extension},
            )

    return DialplanDecision(action='hangup', destination='NO_ROUTE', details={'type': 'no_route'})


def _trunk_for_did(called_number: str) -> SIPTrunk | None:
    """Find the active SIP trunk that has this DID in its inbound_numbers list."""
    if not called_number:
        return None
    for trunk in SIPTrunk.objects.filter(is_active=True):
        if called_number in (trunk.inbound_numbers or []):
            return trunk
    return None


def _queue_for_number(called_number: str) -> CallQueue | None:
    if not called_number:
        return CallQueue.objects.filter(is_active=True).order_by('id').first()
    return CallQueue.objects.filter(is_active=True, name__iexact=called_number).order_by('id').first()


# ---------------------------------------------------------------------------
# XML builders
# ---------------------------------------------------------------------------

def _x(s) -> str:
    return _sax.escape(str(s), {'"': '&quot;'})


def build_dialplan_xml(tenant_slug: str, decision: DialplanDecision) -> str:
    slug = _x(tenant_slug)
    body = _dialplan_extensions(slug, decision)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<document type="freeswitch/xml">\n'
        '  <section name="dialplan" description="CRM Dialplan">\n'
        '    <context name="default">\n'
        f'{body}\n'
        '    </context>\n'
        '  </section>\n'
        '</document>'
    )


def _dialplan_extensions(slug: str, decision: DialplanDecision) -> str:
    if decision.action == 'bridge':
        dest = _x(decision.destination)
        return (
            '      <extension name="crm_route" continue="false">\n'
            '        <condition field="destination_number" expression=".*">\n'
            f'          <action application="set" data="tenant_slug={slug}"/>\n'
            '          <action application="set" data="hangup_after_bridge=true"/>\n'
            '          <action application="set" data="RECORD_STEREO=true"/>\n'
            '          <action application="set" data="record_file=/var/lib/freeswitch/recordings/${uuid}.wav"/>\n'
            '          <action application="answer"/>\n'
            '          <action application="record_session" data="/var/lib/freeswitch/recordings/${uuid}.wav"/>\n'
            f'          <action application="bridge" data="{dest}"/>\n'
            '        </condition>\n'
            '      </extension>'
        )

    if decision.action == 'queue':
        queue_name = _x(decision.destination)
        return (
            '      <extension name="crm_queue" continue="false">\n'
            '        <condition field="destination_number" expression=".*">\n'
            f'          <action application="set" data="tenant_slug={slug}"/>\n'
            '          <action application="set" data="RECORD_STEREO=true"/>\n'
            '          <action application="set" data="record_file=/var/lib/freeswitch/recordings/${uuid}.wav"/>\n'
            '          <action application="answer"/>\n'
            '          <action application="record_session" data="/var/lib/freeswitch/recordings/${uuid}.wav"/>\n'
            f'          <action application="callcenter" data="{queue_name}@default"/>\n'
            '        </condition>\n'
            '      </extension>'
        )

    if decision.action == 'ivr':
        return _ivr_extensions(slug, decision)

    return (
        '      <extension name="crm_hangup" continue="false">\n'
        '        <condition field="destination_number" expression=".*">\n'
        '          <action application="hangup" data="NO_ROUTE"/>\n'
        '        </condition>\n'
        '      </extension>'
    )


def _ivr_extensions(slug: str, decision: DialplanDecision) -> str:
    ivr_id = decision.details.get('ivr_id', 0)
    timeout_ms = int(decision.details.get('timeout', 10)) * 1000
    options = decision.details.get('options', [])
    prefix = f'ivr_{ivr_id}'

    tts = decision.details.get('greeting_tts', '')
    audio_url = decision.details.get('greeting_audio_url', '')
    if tts:
        greeting_action = f'          <action application="speak" data="flite|kal|{_x(tts)}"/>'
    elif audio_url:
        greeting_action = f'          <action application="playback" data="{_x(audio_url)}"/>'
    else:
        greeting_action = '          <action application="sleep" data="500"/>'

    lines = [
        f'      <extension name="{prefix}_entry" continue="false">',
        '        <condition field="destination_number" expression=".*">',
        f'          <action application="set" data="tenant_slug={slug}"/>',
        '          <action application="answer"/>',
        greeting_action,
        f'          <action application="play_and_get_digits" data="1 1 3 {timeout_ms} # silence_stream://500 silence_stream://50 ivr_digit [0-9*]"/>',
        f'          <action application="transfer" data="{prefix}_${{ivr_digit}} XML default"/>',
        '        </condition>',
        '      </extension>',
    ]

    for opt in options:
        digit = _x(str(opt.get('digit', '')))
        action_xml = _ivr_option_to_xml(str(opt.get('action', '')))
        lines += [
            f'      <extension name="{prefix}_{digit}" continue="false">',
            f'        <condition field="destination_number" expression="^{prefix}_{digit}$">',
            f'          {action_xml}',
            '        </condition>',
            '      </extension>',
        ]

    # Catch unrecognised digits — loop back to entry
    lines += [
        f'      <extension name="{prefix}_retry" continue="false">',
        f'        <condition field="destination_number" expression="^{prefix}_.*$">',
        f'          <action application="transfer" data="{prefix}_entry XML default"/>',
        '        </condition>',
        '      </extension>',
    ]
    return '\n'.join(lines)


def _ivr_option_to_xml(action: str) -> str:
    if ':' in action:
        kind, target = action.split(':', 1)
        target = _x(target.strip())
    else:
        kind, target = action.strip(), ''

    if kind == 'queue':
        return f'<action application="callcenter" data="{target}@default"/>'
    if kind == 'extension':
        return f'<action application="bridge" data="user/{target}"/>'
    if kind == 'ivr':
        return f'<action application="transfer" data="{target} XML default"/>'
    # hangup or unknown
    return '<action application="hangup" data="NORMAL_CLEARING"/>'


def build_directory_xml(tenant: Tenant | None, extension_num: str, domain: str) -> str:
    if not tenant or not extension_num:
        return XML_NOT_FOUND

    with tenant_context(tenant):
        ext = (
            PhoneExtension.objects
            .filter(extension=extension_num, is_active=True)
            .select_related('manager')
            .first()
        )

    if not ext:
        return XML_NOT_FOUND

    # Prefer per-tenant SIP domain for isolation; fall back to the domain FS sent us
    effective_domain = (getattr(tenant, 'sip_domain', None) or domain) or domain
    domain_x = _x(effective_domain)
    ext_x = _x(ext.extension)
    password_x = _x(ext.sip_password)
    slug_x = _x(tenant.slug)
    name_x = _x(getattr(ext.manager, 'crm_user_name', None) or ext.extension)

    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<document type="freeswitch/xml">\n'
        '  <section name="directory">\n'
        f'    <domain name="{domain_x}">\n'
        f'      <user id="{ext_x}">\n'
        '        <params>\n'
        f'          <param name="password" value="{password_x}"/>\n'
        f'          <param name="vm-password" value="{ext_x}"/>\n'
        '        </params>\n'
        '        <variables>\n'
        '          <variable name="toll_allow" value="domestic,international,local"/>\n'
        '          <variable name="user_context" value="default"/>\n'
        f'          <variable name="effective_caller_id_name" value="{name_x}"/>\n'
        f'          <variable name="effective_caller_id_number" value="{ext_x}"/>\n'
        f'          <variable name="tenant_slug" value="{slug_x}"/>\n'
        '        </variables>\n'
        '      </user>\n'
        '    </domain>\n'
        '  </section>\n'
        '</document>'
    )


# ---------------------------------------------------------------------------
# Sofia configuration XML (gateway definitions for all tenants)
# ---------------------------------------------------------------------------

def build_configuration_xml() -> str:
    """Return a FreeSWITCH sofia.conf XML with all active SIP gateways.

    FreeSWITCH calls this via the xml_curl 'configuration' binding at startup
    and on 'sofia rescan'. Each gateway carries a tenant_slug inbound variable
    so the dialplan can resolve the correct tenant on incoming PSTN calls.
    """
    gateways: list[str] = []

    with schema_context('public'):
        tenants = list(Tenant.objects.filter(is_active=True))

    for tenant in tenants:
        with tenant_context(tenant):
            trunks = list(SIPTrunk.objects.filter(is_active=True))
        slug = _x(tenant.slug)
        sip_domain = _x(getattr(tenant, 'sip_domain', '') or '')
        for trunk in trunks:
            creds = trunk.credentials or {}
            name = _x(trunk.name)
            username = _x(creds.get('username', ''))
            password = _x(creds.get('password', ''))
            proxy = _x(creds.get('proxy', ''))
            realm_line = (
                f'                <param name="realm" value="{sip_domain}"/>\n'
                if sip_domain else ''
            )
            gateways.append(
                f'              <gateway name="{name}">\n'
                f'                <param name="username" value="{username}"/>\n'
                f'                <param name="password" value="{password}"/>\n'
                f'                <param name="proxy" value="{proxy}"/>\n'
                f'{realm_line}'
                f'                <param name="register" value="true"/>\n'
                f'                <variables>\n'
                f'                  <variable name="tenant_slug" value="{slug}" direction="inbound"/>\n'
                f'                </variables>\n'
                f'              </gateway>\n'
            )

    if not gateways:
        return XML_NOT_FOUND

    gateways_xml = ''.join(gateways)
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        '<document type="freeswitch/xml">\n'
        '  <section name="configuration">\n'
        '    <configuration name="sofia.conf" description="CRM SIP Gateways">\n'
        '      <profiles>\n'
        '        <profile name="external">\n'
        '          <gateways>\n'
        f'{gateways_xml}'
        '          </gateways>\n'
        '        </profile>\n'
        '      </profiles>\n'
        '    </configuration>\n'
        '  </section>\n'
        '</document>'
    )

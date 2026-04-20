-- CDR hook: fires on CHANNEL_HANGUP_COMPLETE and POSTs call data to Django.
-- Loaded via: freeswitch.conf.xml or dialplan action application="lua" data="cdr_hook.lua"
-- For automatic firing on every call end, add to autoload_configs/lua.conf.xml:
--   <hook event="CHANNEL_HANGUP_COMPLETE" script="cdr_hook.lua"/>

local http   = require("socket.http")
local ltn12  = require("ltn12")

local function getvar(name)
    local ok, val = pcall(function() return session:getVariable(name) end)
    return (ok and val) or ""
end

local uuid        = getvar("uuid")
local caller      = getvar("caller_id_number")
local destination = getvar("destination_number")
local billsec     = getvar("billsec")
local direction   = getvar("call_direction")
local hangup      = getvar("hangup_cause")
local tenant_slug = getvar("tenant_slug")
local record_file = getvar("record_file")

-- Determine result from hangup cause and answered duration
local result = "answered"
if billsec == "" or billsec == "0" or billsec == nil then
    result = "missed"
elseif hangup ~= "NORMAL_CLEARING" and hangup ~= "SUCCESS" then
    result = "missed"
end

local token   = os.getenv("ESL_PASSWORD") or "ClueCon"
local body    = string.format(
    '{"uuid":"%s","caller_number":"%s","called_number":"%s",' ..
    '"duration":%s,"result":"%s","tenant_slug":"%s","direction":"%s","record_file":"%s"}',
    uuid, caller, destination,
    (billsec == "" and "0" or billsec),
    result, tenant_slug,
    (direction == "" and "inbound" or direction),
    (record_file or "")
)

local resp = {}
local ok, err = http.request({
    url    = "http://web:8000/telephony/events/",
    method = "POST",
    headers = {
        ["Content-Type"]       = "application/json",
        ["Content-Length"]     = tostring(#body),
        ["X-FreeSWITCH-Token"] = token,
    },
    source = ltn12.source.string(body),
    sink   = ltn12.sink.table(resp),
})

if not ok then
    freeswitch.consoleLog("ERR", "[cdr_hook] POST to Django failed: " .. tostring(err) .. "\n")
end

<template>
  <FeatureGate feature="crm_builtin" class="crm-gate">
    <section class="crm-section">
      <h1 class="page-title brand-heading">Встроенный CRM</h1>

      <div class="tabs-bar">
        <button v-for="t in tabs" :key="t.key" :class="['tab-btn', { active: tab === t.key }]" @click="tab = t.key">{{ t.label }}</button>
      </div>

      <div v-if="!hasAnyCrmAccess" class="surface-card" style="padding: 14px; margin-bottom: 12px;">
        У вас нет прав для просмотра CRM-сущностей.
      </div>

      <!-- KANBAN TAB -->
      <div v-if="tab === 'kanban' && canViewDeals" class="tab-content kanban-tab">
        <div class="toolbar">
          <PSelect v-model="selectedPipeline" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="loadBoard" class="toolbar-select" />
          <PButton v-if="canCreateDeal" label="Новая сделка" icon="pi pi-plus" size="small" @click="openDealForm" />
          <div style="margin-left: auto; display: flex; gap: 4px">
            <PButton :icon="kanbanViewMode === 'board' ? 'pi pi-th-large' : 'pi pi-list'" size="small" outlined @click="kanbanViewMode = kanbanViewMode === 'board' ? 'list' : 'board'" />
            <PButton icon="pi pi-filter" size="small" :outlined="!showKanbanFilters" @click="showKanbanFilters = !showKanbanFilters" />
          </div>
        </div>

        <!-- Kanban Filters -->
        <div v-if="showKanbanFilters" class="kanban-filters">
          <PSelect v-model="kanbanFilter.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="Источник" showClear class="filter-field" />
          <PSelect v-model="kanbanFilter.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="Контакт" showClear filter filterPlaceholder="Поиск…" class="filter-field" />
          <PSelect v-model="kanbanFilter.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="Компания" showClear filter filterPlaceholder="Поиск…" class="filter-field" />
          <PSelect v-model="kanbanFilter.date" :options="dateFilterOptions" optionLabel="label" optionValue="value" placeholder="Дата" showClear class="filter-field" />
        </div>

        <!-- Kanban Board View -->
        <div v-if="kanbanViewMode === 'board'" class="kanban" :class="{ 'has-filters': showKanbanFilters }">
          <div v-for="col in filteredKanbanColumns" :key="col.stage.id" class="kanban-col surface-card"
            @dragover.prevent @drop="onDrop($event, col.stage.id)">
            <header>
              <span class="stage-dot" :style="{ background: col.stage.color }" />
              <strong>{{ col.stage.name }}</strong>
              <span class="badge-count">{{ col.deals.length }}</span>
            </header>
            <div class="kanban-col-body">
              <div
                v-for="deal in col.deals" :key="deal.id" class="deal-card surface-card"
                :draggable="canUpdateDeal" @dragstart="canUpdateDeal && onDragStart($event, deal.id)" @click="openDeal(deal.id)">
                <div class="deal-name">{{ deal.name }}</div>
                <div class="deal-amount" v-if="deal.amount">{{ deal.amount.toLocaleString() }} {{ deal.currency }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Kanban List View -->
        <div v-else-if="kanbanViewMode === 'list'" class="kanban-list">
          <PDataTable
            :value="flatDealsList"
            size="small"
            stripedRows
            :paginator="true"
            :rows="25"
            :rowsPerPageOptions="[10, 25, 50]"
            sortMode="single"
            sortField="stage_name"
            :sortOrder="1"
          >
            <PColumn field="name" header="Сделка" sortable>
              <template #body="{ data }">
                <a class="deal-link" @click.prevent="openDeal(data.id)">{{ data.name }}</a>
              </template>
            </PColumn>
            <PColumn field="stage_name" header="Этап" sortable>
              <template #body="{ data }">
                <span class="stage-dot" :style="{ background: data._stage_color }" />
                {{ data.stage_name }}
              </template>
            </PColumn>
            <PColumn field="amount" header="Сумма" sortable>
              <template #body="{ data }">
                {{ data.amount ? data.amount.toLocaleString() + ' ' + data.currency : '—' }}
              </template>
            </PColumn>
            <PColumn field="source" header="Источник" sortable />
            <PColumn field="created_at" header="Дата создания" sortable>
              <template #body="{ data }">
                {{ data.created_at ? formatDate(data.created_at) : '' }}
              </template>
            </PColumn>
          </PDataTable>
        </div>

        <div v-if="!kanbanColumns.length" class="empty-state">Выберите воронку для загрузки Kanban</div>
      </div>

      <!-- CONTACTS TAB -->
      <div v-if="tab === 'contacts' && canViewContacts" class="tab-content">
        <div class="toolbar">
          <PInputText v-model="contactSearch" placeholder="Поиск по имени/телефону" @keyup.enter="loadContacts" />
          <PButton v-if="canCreateContact" label="Новый контакт" icon="pi pi-plus" size="small" @click="showContactForm = true" />
        </div>
        <PDataTable :value="contacts" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="first_name" header="Имя" />
          <PColumn field="last_name" header="Фамилия" />
          <PColumn field="phone" header="Телефон" />
          <PColumn field="email" header="Email" />
          <PColumn header="ЭДО">
            <template #body="{ data }">
              <span v-if="data.esign_agreement_signed_at" style="color: var(--p-green-500);" title="Соглашение подписано">✅</span>
              <span v-else style="color: var(--text-muted);" title="Соглашение не подписано">—</span>
            </template>
          </PColumn>
          <PColumn header="">
            <template #body="{ data }">
              <PButton icon="pi pi-eye" text size="small" @click="openContact(data.id)" />
              <PButton v-if="canUpdateContact" icon="pi pi-pencil" text size="small" @click="editContact(data)" />
              <PButton v-if="canDeleteContact" icon="pi pi-trash" text size="small" severity="danger" @click="removeContact(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- COMPANIES TAB -->
      <div v-if="tab === 'companies' && canViewCompanies" class="tab-content">
        <div class="toolbar">
          <PInputText v-model="companySearch" placeholder="Поиск по названию/ИНН" @keyup.enter="loadCompanies" />
          <PButton v-if="canCreateCompany" label="Новая компания" icon="pi pi-plus" size="small" @click="showCompanyForm = true" />
        </div>
        <PDataTable :value="companies" size="small" stripedRows :paginator="true" :rows="20" :rowsPerPageOptions="[10, 20, 50]">
          <PColumn field="name" header="Название" />
          <PColumn field="inn" header="ИНН" />
          <PColumn field="phone" header="Телефон" />
          <PColumn field="email" header="Email" />
          <PColumn header="">
            <template #body="{ data }">
              <PButton v-if="canUpdateCompany" icon="pi pi-pencil" text size="small" @click="editCompany(data)" />
              <PButton v-if="canDeleteCompany" icon="pi pi-trash" text size="small" severity="danger" @click="removeCompany(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
      </div>

      <!-- PIPELINES TAB -->
      <div v-if="tab === 'pipelines' && canManagePipelines" class="tab-content">
        <div class="toolbar">
          <PButton label="Новая воронка" icon="pi pi-plus" size="small" @click="showPipelineForm = true" />
        </div>
        <div v-for="p in pipelines" :key="p.id" class="surface-card" style="padding: 14px; margin-bottom: 10px">
          <div style="display: flex; justify-content: space-between; align-items: center">
            <strong>{{ p.name }}</strong>
            <div>
              <PButton icon="pi pi-cog" text size="small" @click="editPipelineStages(p)" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removePipeline(p.id)" />
            </div>
          </div>
          <div v-if="selectedPipelineStages && selectedPipelineStagesFor === p.id" style="margin-top: 10px">
            <div
              v-for="(s, idx) in selectedPipelineStages" :key="s.id"
              class="stage-row-draggable"
              draggable="true"
              @dragstart="onStageDragStart($event, idx)"
              @dragover.prevent
              @drop="onStageDrop($event, idx, p.id)"
            >
              <span class="stage-drag-handle">⠿</span>
              <span class="stage-dot" :style="{ background: s.color }" />
              <span class="stage-name-text">{{ s.name }}</span>
              <PTag :value="stageTypeLabel(s.stage_type)" :severity="stageTypeSeverity(s.stage_type)" class="stage-type-tag" />
              <PTag v-if="triggerLabel(s)" :value="triggerLabel(s)" severity="warn" size="small" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="removeStage(s.id, p.id)" />
            </div>
            <div style="margin-top: 8px; display: flex; gap: 6px">
              <PInputText v-model="newStageName" placeholder="Новая стадия" size="small" />
              <PButton label="Добавить" size="small" @click="addStage(p.id)" />
            </div>
          </div>
        </div>
      </div>

      <!-- TRIGGERS TAB -->
      <div v-if="tab === 'triggers' && canManageTriggers" class="tab-content">
        <div class="toolbar">
          <PButton label="Новый триггер" icon="pi pi-plus" size="small" @click="openNewTrigger" />
        </div>
        <PDataTable :value="allTriggers" size="small" stripedRows :paginator="allTriggers.length > 20" :rows="20">
          <PColumn field="pipeline_name" header="Воронка" />
          <PColumn field="stage_name" header="Этап">
            <template #body="{ data }">
              <span class="stage-dot" :style="{ background: data.stage_color }" />
              {{ data.stage_name }}
            </template>
          </PColumn>
          <PColumn field="action_label" header="Действие" />
          <PColumn header="Параметры">
            <template #body="{ data }">
              <span v-if="data.action_type === 'create_task'">{{ data.action_title }} (через {{ data.action_days_offset }} дн.)</span>
              <span v-else-if="data.action_type === 'send_notification'">Событие: {{ data.action_event }}</span>
              <span v-else>—</span>
            </template>
          </PColumn>
          <PColumn header="" style="width: 100px">
            <template #body="{ data }">
              <PButton icon="pi pi-pencil" text size="small" @click="editTrigger(data)" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="deleteTrigger(data)" />
            </template>
          </PColumn>
        </PDataTable>
        <div v-if="!allTriggers.length" class="empty-state">Нет настроенных триггеров</div>
      </div>

      <!-- TASKS TAB -->
      <div v-if="tab === 'tasks' && canUseTasks" class="tab-content">
        <div class="toolbar">
          <PSelect v-model="tasksStatusFilter" :options="taskStatusOptions" optionLabel="label" optionValue="value" placeholder="Все статусы" showClear class="toolbar-select" @change="loadTasks" />
          <PButton label="Новая задача" icon="pi pi-plus" size="small" @click="showTaskDialog = true" />
        </div>
        <PDataTable :value="tasksList" size="small" stripedRows :paginator="tasksList.length > 20" :rows="20">
          <PColumn field="title" header="Задача">
            <template #body="{ data }">
              <a v-if="data.deal_id" class="deal-link" @click.prevent="openDeal(data.deal_id)">{{ data.title }}</a>
              <span v-else>{{ data.title }}</span>
            </template>
          </PColumn>
          <PColumn field="status" header="Статус">
            <template #body="{ data }">
              <PTag :value="taskStatusLabel(data.status)" :severity="taskStatusSeverity(data.status)" />
            </template>
          </PColumn>
          <PColumn field="due_date" header="Срок">
            <template #body="{ data }">
              {{ data.due_date ? formatDate(data.due_date) : '—' }}
            </template>
          </PColumn>
          <PColumn field="created_at" header="Создана">
            <template #body="{ data }">
              {{ formatDate(data.created_at) }}
            </template>
          </PColumn>
          <PColumn header="" style="width: 100px">
            <template #body="{ data }">
              <PButton v-if="data.status === 'planned'" icon="pi pi-check" text size="small" title="Выполнено" @click="completeTask(data.id)" />
              <PButton icon="pi pi-trash" text size="small" severity="danger" @click="deleteTask(data.id)" />
            </template>
          </PColumn>
        </PDataTable>
        <div v-if="!tasksList.length" class="empty-state">Нет задач</div>
      </div>

      <!-- STATS TAB -->
      <div v-if="tab === 'stats' && canUseStats" class="tab-content">
        <div class="toolbar">
          <PSelect v-model="statsPipelineId" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="loadStats" class="toolbar-select" />
        </div>

        <div v-if="pipelineStatsData.length" class="stats-section">
          <h4>Конверсия по воронке</h4>
          <PDataTable :value="pipelineStatsData" size="small" stripedRows>
            <PColumn field="stage_name" header="Этап" />
            <PColumn field="total" header="Сделок" />
            <PColumn field="amount" header="Сумма">
              <template #body="{ data }">
                {{ data.amount ? data.amount.toLocaleString() + ' ₽' : '—' }}
              </template>
            </PColumn>
            <PColumn header="Доля">
              <template #body="{ data }">
                <div style="display: flex; align-items: center; gap: 8px">
                  <PProgressBar :value="pipelineTotal ? Math.round(data.total / pipelineTotal * 100) : 0" :showValue="true" style="flex: 1; height: 20px" />
                </div>
              </template>
            </PColumn>
          </PDataTable>
        </div>

        <div v-if="managerStatsData.length" class="stats-section">
          <h4>Сделки по менеджерам</h4>
          <PDataTable :value="managerStatsData" size="small" stripedRows>
            <PColumn field="manager_name" header="Менеджер">
              <template #body="{ data }">
                {{ data.manager_name || 'Не назначен' }}
              </template>
            </PColumn>
            <PColumn field="total" header="Сделок" />
            <PColumn field="amount" header="Сумма">
              <template #body="{ data }">
                {{ data.amount ? data.amount.toLocaleString() + ' ₽' : '—' }}
              </template>
            </PColumn>
          </PDataTable>
        </div>

        <div v-if="!pipelineStatsData.length && !managerStatsData.length" class="empty-state">Выберите воронку для просмотра статистики</div>
      </div>

      <!-- CONTACT DETAIL DIALOG -->
      <PDialog v-model:visible="showContactDetail" header="Контакт" :style="{ width: '600px', maxWidth: '95vw' }" modal>
        <div v-if="contactDetail" class="form-grid">
          <div class="form-row-2">
            <div><span class="field-label">Имя:</span> {{ contactDetail.first_name }} {{ contactDetail.last_name }}</div>
            <div><span class="field-label">Телефон:</span> {{ contactDetail.phone || '—' }}</div>
          </div>
          <div class="form-row-2">
            <div><span class="field-label">Email:</span> {{ contactDetail.email || '—' }}</div>
            <div><span class="field-label">Источник:</span> {{ contactDetail.source || '—' }}</div>
          </div>
          <div class="form-row-2" style="margin-top: 8px;">
            <div>
              <span class="field-label">Электронный документооборот:</span>
              <span v-if="(contactDetail as any).esign_agreement_signed_at" style="color: var(--p-green-500); font-weight: 600;">
                ✅ Соглашение подписано {{ formatDate((contactDetail as any).esign_agreement_signed_at) }}
                <a href="#" @click.prevent="downloadDealContractPdf((contactDetail as any).esign_agreement_id)" style="margin-left: 8px; font-weight: 400; text-decoration: underline; cursor: pointer;" title="Скачать соглашение">Скачать PDF</a>
              </span>
              <span v-else style="color: var(--p-orange-500);">⚠️ Соглашение не подписано</span>
            </div>
          </div>
          <PDivider />
          <div class="activity-section">
            <h4>Лог активности</h4>
            <div class="activity-list">
              <div v-for="a in contactDetail.activities" :key="a.id" class="timeline-item">
                <span class="tl-icon" :class="a.type">{{ activityIcon(a.type) }}</span>
                <div class="tl-content">
                  <strong>{{ a.title }}</strong>
                  <div class="tl-meta">
                    <span class="tl-date">{{ formatDateTime(a.created_at) }}</span>
                    <PTag :value="activityTypeLabel(a.type)" size="small" />
                  </div>
                </div>
              </div>
              <div v-if="!contactDetail.activities?.length" class="empty-state">Нет активностей</div>
            </div>
          </div>
        </div>
      </PDialog>

      <!-- DEAL DETAIL / EDIT DIALOG -->
      <PDialog v-model:visible="showDealDetail" header="Сделка" :style="{ width: '640px', maxWidth: '95vw' }" modal>
        <div v-if="dealDetail" class="form-grid">
          <div>
            <label class="field-label">Название *</label>
            <PInputText v-model="dealEdit.name" class="w-full" :disabled="!canUpdateDeal" />
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Сумма</label>
              <PInputText v-model.number="dealEdit.amount" type="number" class="w-full" :disabled="!canUpdateDeal" />
            </div>
            <div>
              <label class="field-label">Валюта</label>
              <PSelect v-model="dealEdit.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" :disabled="!canUpdateDeal" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Контакт</label>
              <div class="select-with-add">
                <PSelect v-model="dealEdit.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
                <PButton v-if="canCreateContact && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'edit-contact'; showQuickContact = true" />
              </div>
            </div>
            <div>
              <label class="field-label">Компания</label>
              <div class="select-with-add">
                <PSelect v-model="dealEdit.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" :disabled="!canUpdateDeal" />
                <PButton v-if="canCreateCompany && canUpdateDeal" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'edit-company'; showQuickCompany = true" />
              </div>
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Ответственный</label>
              <PSelect v-model="dealEdit.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" :disabled="!canUpdateDeal" />
            </div>
            <div>
              <label class="field-label">Дата закрытия</label>
              <PInputText v-model="dealEdit.expected_close_date" type="date" class="w-full" :disabled="!canUpdateDeal" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Источник</label>
              <PSelect v-model="dealEdit.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" :disabled="!canUpdateDeal" />
            </div>
            <div>
              <label class="field-label">Причина проигрыша</label>
              <PInputText v-model="dealEdit.loss_reason" class="w-full" :disabled="!canUpdateDeal" />
            </div>
          </div>
          <div style="display: flex; gap: 8px; justify-content: flex-end">
            <PButton v-if="canUpdateDeal" label="Договор" icon="pi pi-file" size="small" outlined @click="openDealContract" />
            <PButton v-if="canUpdateDeal" label="Сохранить" icon="pi pi-check" size="small" @click="saveDealEdit" />
            <PButton v-if="canDeleteDeal" label="Удалить" icon="pi pi-trash" size="small" severity="danger" outlined @click="removeDeal" />
          </div>

          <!-- Contracts associated with this deal -->
          <div v-if="dealDetail.contracts?.length" class="deal-contracts-section">
            <PDivider />
            <h4>Договоры</h4>
            <div v-for="c in dealDetail.contracts" :key="c.id" class="deal-contract-item">
              <span class="deal-contract-name">📄 {{ c.template_name || 'Договор' }} #{{ c.id }}</span>
              <span :class="'status-badge status-' + c.status">{{ contractStatusLabel(c.status) }}</span>
              <span class="deal-contract-date">{{ formatDate(c.created_at) }}</span>
              <PButton v-if="c.status === 'draft' || c.status === 'viewed'" icon="pi pi-send" text size="small" @click="openDealSigningDialog(c)" title="Отправить на подпись" />
              <PButton icon="pi pi-eye" text size="small" @click="previewDealContract(c.id)" title="Просмотр" />
              <PButton icon="pi pi-download" text size="small" @click="downloadDealContractPdf(c.id)" title="Скачать PDF" />
            </div>
          </div>

          <!-- Chat sessions linked to this deal -->
          <div v-if="dealDetail.chat_sessions?.length" class="deal-contracts-section">
            <PDivider />
            <h4>Чаты</h4>
            <div v-for="cs in dealDetail.chat_sessions" :key="cs.id" class="deal-contract-item">
              <span class="deal-contract-name">💬 {{ cs.external_user_name || cs.external_chat_id }}</span>
              <PTag :value="cs.channel_name" size="small" />
              <span class="deal-contract-date">{{ cs.last_message_at ? formatDateTime(cs.last_message_at) : '' }}</span>
              <router-link :to="{ name: 'channels', query: { tab: 'chats', channel: cs.channel_id, session: cs.id } }" style="text-decoration: none">
                <PButton icon="pi pi-comments" text size="small" title="Открыть чат" />
              </router-link>
            </div>
          </div>

          <!-- Contract preview dialog -->
          <PDialog v-model:visible="showDealContractPreview" header="Просмотр договора" :style="{ width: '700px', maxWidth: '95vw' }" modal>
            <div v-html="dealContractPreviewHtml" style="padding: 12px; max-height: 60vh; overflow: auto;" />
          </PDialog>

          <!-- Deal contract signing dialog -->
          <PDialog v-model:visible="showDealSigningDialog" header="Отправить на подпись" :style="{ width: '520px', maxWidth: '95vw' }" modal>
            <div class="form-grid">
              <p>Договор #{{ dealSigningContract?.id }} — {{ contractStatusLabel(dealSigningContract?.status as string) }}</p>

              <template v-if="!dealSigningUrl">
                <div>
                  <label class="field-label">Телефон получателя</label>
                  <PInputText v-model="dealSigningRecipient" class="w-full" placeholder="+79001234567" />
                </div>
                <PButton label="Сформировать ссылку" icon="pi pi-link" @click="dealSendForSigning" :disabled="!dealSigningRecipient" />
                <div v-if="dealSigningError" style="color: #991b1b;">{{ dealSigningError }}</div>
              </template>

              <template v-else>
                <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 10px 14px; border-radius: 8px; margin-bottom: 4px;">
                  <label class="field-label">Ссылка для подписания</label>
                  <div style="display: flex; gap: 6px; align-items: center">
                    <PInputText :modelValue="dealSigningUrl" class="w-full" readonly />
                    <PButton icon="pi pi-copy" text size="small" @click="copyDealSigningLink" title="Скопировать" />
                  </div>
                  <p style="color: #6b7280; font-size: 12px; margin: 4px 0 0">Скопируйте ссылку и отправьте клиенту. Клиент откроет её, запросит код и подпишет договор.</p>
                </div>
              </template>
            </div>
          </PDialog>

          <PDivider />
          <div class="activity-section">
            <h4>Лог активности</h4>
            <div class="activity-list">
              <div v-for="a in dealDetail.activities" :key="a.id" class="timeline-item">
                <span class="tl-icon" :class="a.type">{{ activityIcon(a.type) }}</span>
                <div class="tl-content">
                  <strong>{{ a.title }}</strong>
                  <div v-if="(a as any).body" class="tl-body">{{ (a as any).body }}</div>
                  <div class="tl-meta">
                    <span class="tl-date">{{ formatDateTime(a.created_at) }}</span>
                    <PTag :value="activityTypeLabel(a.type)" size="small" />
                  </div>
                </div>
              </div>
              <div v-if="!dealDetail.activities?.length" class="empty-state">Нет активностей</div>
            </div>
            <div class="add-activity-row">
              <PSelect v-model="newActivityType" :options="activityTypeOptions" optionLabel="label" optionValue="value" placeholder="Тип" class="activity-type-select" :disabled="!canUpdateDeal" />
              <PInputText v-model="newNote" :placeholder="newActivityType === 'note' ? 'Заметка...' : 'Описание...'" style="flex: 1" :disabled="!canUpdateDeal" />
              <PButton v-if="canUpdateDeal" label="Добавить" size="small" @click="addNote" />
            </div>
          </div>
        </div>
      </PDialog>

      <!-- NEW DEAL FORM -->
      <PDialog v-model:visible="showDealForm" header="Новая сделка" :style="{ width: '500px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Название сделки *</label>
            <PInputText v-model="dealForm.name" placeholder="Название сделки" class="w-full" />
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Воронка *</label>
              <PSelect v-model="dealForm.pipeline_id" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Воронка" @change="onDealPipelineChange" class="w-full" />
            </div>
            <div>
              <label class="field-label">Стадия</label>
              <PSelect v-model="dealForm.stage_id" :options="dealFormStageOptions" optionLabel="label" optionValue="value" placeholder="Первая стадия" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Сумма</label>
              <PInputText v-model.number="dealForm.amount" placeholder="0" type="number" class="w-full" />
            </div>
            <div>
              <label class="field-label">Валюта</label>
              <PSelect v-model="dealForm.currency" :options="currencies" optionLabel="label" optionValue="value" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Контакт</label>
              <div class="select-with-add">
                <PSelect v-model="dealForm.contact_id" :options="contactOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
                <PButton v-if="canCreateContact" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-contact'; showQuickContact = true" />
              </div>
            </div>
            <div>
              <label class="field-label">Компания</label>
              <div class="select-with-add">
                <PSelect v-model="dealForm.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
                <PButton v-if="canCreateCompany" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'deal-company'; showQuickCompany = true" />
              </div>
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Ответственный</label>
              <PSelect v-model="dealForm.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" />
            </div>
            <div>
              <label class="field-label">Дата закрытия</label>
              <PInputText v-model="dealForm.expected_close_date" type="date" class="w-full" />
            </div>
          </div>
          <div>
            <label class="field-label">Источник</label>
            <PSelect v-model="dealForm.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" />
          </div>
          <PButton label="Создать" @click="submitDeal" :disabled="!canCreateDeal" />
        </div>
      </PDialog>

      <!-- NEW CONTACT FORM -->
      <PDialog v-model:visible="showContactForm" header="Контакт" :style="{ width: '500px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div class="form-row-2">
            <div>
              <label class="field-label">Имя *</label>
              <PInputText v-model="contactForm.first_name" placeholder="Имя" class="w-full" />
            </div>
            <div>
              <label class="field-label">Фамилия</label>
              <PInputText v-model="contactForm.last_name" placeholder="Фамилия" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Телефон</label>
              <PInputText v-model="contactForm.phone" placeholder="+7 (___) ___-__-__" class="w-full" />
            </div>
            <div>
              <label class="field-label">Email</label>
              <PInputText v-model="contactForm.email" placeholder="email@example.com" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Должность</label>
              <PInputText v-model="contactForm.position" placeholder="Менеджер, директор..." class="w-full" />
            </div>
            <div>
              <label class="field-label">Компания</label>
              <div class="select-with-add">
                <PSelect v-model="contactForm.company_id" :options="companyOptions" optionLabel="label" optionValue="value" placeholder="— не выбрана —" showClear filter filterPlaceholder="Поиск…" class="flex-1" />
                <PButton v-if="canCreateCompany" icon="pi pi-plus" size="small" outlined @click="quickCreateTarget = 'contact-company'; showQuickCompany = true" />
              </div>
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Мессенджер</label>
              <PInputText v-model="contactForm.messenger_id" placeholder="Telegram, WhatsApp..." class="w-full" />
            </div>
            <div>
              <label class="field-label">Источник</label>
              <PSelect v-model="contactForm.source" :options="sourceOptions" optionLabel="label" optionValue="value" placeholder="— не указан —" showClear class="w-full" />
            </div>
          </div>
          <div>
            <label class="field-label">Ответственный</label>
            <PSelect v-model="contactForm.responsible_id" :options="managerOptions" optionLabel="label" optionValue="value" placeholder="— не выбран —" showClear class="w-full" />
          </div>
          <PButton :label="contactForm.id ? 'Сохранить' : 'Создать'" @click="submitContact" :disabled="contactForm.id ? !canUpdateContact : !canCreateContact" />
        </div>
      </PDialog>

      <!-- NEW COMPANY FORM -->
      <PDialog v-model:visible="showCompanyForm" header="Компания" :style="{ width: '450px' }" modal>
        <div class="form-grid">
          <PInputText v-model="companyForm.name" placeholder="Название" />
          <PInputText v-model="companyForm.inn" placeholder="ИНН" />
          <PInputText v-model="companyForm.phone" placeholder="Телефон" />
          <PInputText v-model="companyForm.email" placeholder="Email" />
          <PButton :label="companyForm.id ? 'Сохранить' : 'Создать'" @click="submitCompany" :disabled="companyForm.id ? !canUpdateCompany : !canCreateCompany" />
        </div>
      </PDialog>

      <!-- QUICK CREATE CONTACT -->
      <PDialog v-model:visible="showQuickContact" header="Быстрое создание контакта" :style="{ width: '400px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div class="form-row-2">
            <div>
              <label class="field-label">Имя *</label>
              <PInputText v-model="quickContact.first_name" placeholder="Имя" class="w-full" />
            </div>
            <div>
              <label class="field-label">Фамилия</label>
              <PInputText v-model="quickContact.last_name" placeholder="Фамилия" class="w-full" />
            </div>
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">Телефон</label>
              <PInputText v-model="quickContact.phone" placeholder="+7..." class="w-full" />
            </div>
            <div>
              <label class="field-label">Email</label>
              <PInputText v-model="quickContact.email" placeholder="email@..." class="w-full" />
            </div>
          </div>
          <PButton label="Создать" @click="submitQuickContact" :disabled="!canCreateContact" />
        </div>
      </PDialog>

      <!-- QUICK CREATE COMPANY -->
      <PDialog v-model:visible="showQuickCompany" header="Быстрое создание компании" :style="{ width: '400px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Название *</label>
            <PInputText v-model="quickCompany.name" placeholder="Название" class="w-full" />
          </div>
          <div class="form-row-2">
            <div>
              <label class="field-label">ИНН</label>
              <PInputText v-model="quickCompany.inn" placeholder="ИНН" maxlength="12" class="w-full" />
            </div>
            <div>
              <label class="field-label">Телефон</label>
              <PInputText v-model="quickCompany.phone" placeholder="+7..." class="w-full" />
            </div>
          </div>
          <PButton label="Создать" @click="submitQuickCompany" :disabled="!canCreateCompany" />
        </div>
      </PDialog>

      <!-- NEW PIPELINE FORM -->
      <PDialog v-model:visible="showPipelineForm" header="Новая воронка" :style="{ width: '400px' }" modal>
        <div class="form-grid">
          <PInputText v-model="pipelineForm.name" placeholder="Название воронки" />
          <PButton label="Создать" @click="submitPipeline" />
        </div>
      </PDialog>

      <!-- TRIGGER CONFIG DIALOG -->
      <PDialog v-model:visible="showTriggerConfig" header="Триггер" :style="{ width: '450px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div v-if="!triggerStage">
            <label class="field-label">Воронка *</label>
            <PSelect v-model="triggerPipelineId" :options="pipelines" optionLabel="name" optionValue="id" placeholder="Выберите воронку" @change="onTriggerPipelineChange" class="w-full" />
          </div>
          <div v-if="!triggerStage">
            <label class="field-label">Этап *</label>
            <PSelect v-model="triggerStageId" :options="triggerStageOptions" optionLabel="label" optionValue="value" placeholder="Выберите этап" class="w-full" />
          </div>
          <div v-if="triggerStage">
            <label class="field-label">Этап: {{ triggerStage.name }}</label>
          </div>
          <div>
            <label class="field-label">Действие *</label>
            <PSelect v-model="triggerForm.type" :options="triggerTypeOptions" optionLabel="label" optionValue="value" placeholder="Выберите действие" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_task'">
            <label class="field-label">Название задачи</label>
            <PInputText v-model="triggerForm.title" placeholder="Новая задача" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_task'">
            <label class="field-label">Через дней</label>
            <PInputText v-model.number="triggerForm.days_offset" type="number" min="0" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'send_notification'">
            <label class="field-label">Событие</label>
            <PInputText v-model="triggerForm.event" placeholder="deal_stage_changed" class="w-full" />
          </div>
          <div v-if="triggerForm.type === 'create_contract'">
            <label class="field-label">Шаблон договора *</label>
            <PSelect v-model="triggerForm.template_id" :options="triggerTemplateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
          </div>
          <PButton label="Сохранить" @click="saveTrigger" :disabled="!triggerForm.type || (!triggerStage && !triggerStageId) || (triggerForm.type === 'create_contract' && !triggerForm.template_id)" />
        </div>
      </PDialog>

      <!-- CREATE CONTRACT FROM DEAL -->
      <!-- NEW TASK DIALOG -->
      <PDialog v-model:visible="showTaskDialog" header="Новая задача" :style="{ width: '420px', maxWidth: '95vw' }" modal @hide="resetTaskForm">
        <div class="form-grid">
          <div>
            <label class="field-label">Название *</label>
            <PInputText v-model="newTaskForm.title" class="w-full" placeholder="Название задачи" />
          </div>
          <div>
            <label class="field-label">Описание</label>
            <PTextarea v-model="newTaskForm.body" rows="3" class="w-full" autoResize />
          </div>
          <div>
            <label class="field-label">Срок выполнения</label>
            <PInputText v-model="newTaskForm.due_date" type="date" class="w-full" />
          </div>
        </div>
        <template #footer>
          <PButton label="Отмена" severity="secondary" size="small" @click="showTaskDialog = false" />
          <PButton label="Создать" size="small" :disabled="!newTaskForm.title.trim()" @click="createTask" />
        </template>
      </PDialog>

      <PDialog v-model:visible="showDealContractDialog" header="Создать договор из сделки" :style="{ width: '420px', maxWidth: '95vw' }" modal>
        <div class="form-grid">
          <div>
            <label class="field-label">Шаблон *</label>
            <PSelect v-model="dealContractTemplateId" :options="contractTemplateOptions" optionLabel="label" optionValue="value" placeholder="Выберите шаблон" class="w-full" />
          </div>
          <PButton label="Сгенерировать" icon="pi pi-file" @click="createDealContract" :disabled="!dealContractTemplateId" />
        </div>
      </PDialog>
    </section>

    <template #locked>
      <div class="surface-card" style="padding: 16px">Раздел доступен в плане CRM.</div>
    </template>
  </FeatureGate>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import FeatureGate from '@/components/FeatureGate.vue'
import * as crmApi from '@/api/crm'
import { api, getAccessToken, getTenantSlug } from '@/api/http'
import { useAuthStore } from '@/stores/auth'
import { canViewAnyCrmEntity, normalizeCrmPermissions } from '@/utils/crmPermissions'
import type { CrmContact, CrmCompany, CrmPipeline, CrmStage, KanbanColumn, CrmDeal, CrmActivity } from '@/api/crm'
import { formatDate, formatDateTime } from '@/utils/datetime'

/* --- Shared option lists --- */
const sourceOptions = [
  { label: 'Сайт', value: 'website' },
  { label: 'Телефон', value: 'phone' },
  { label: 'Email', value: 'email' },
  { label: 'Соцсети', value: 'social' },
  { label: 'Рекомендация', value: 'referral' },
  { label: 'Реклама', value: 'ad' },
  { label: 'Другое', value: 'other' },
]
const currencies = [
  { label: 'RUB', value: 'RUB' },
  { label: 'USD', value: 'USD' },
  { label: 'EUR', value: 'EUR' },
]

const authStore = useAuthStore()
const crmPermissions = computed(() => normalizeCrmPermissions(authStore.user?.crm_permissions))
const canViewDeals = computed(() => crmPermissions.value.deals.can_view)
const canCreateDeal = computed(() => crmPermissions.value.deals.can_create)
const canUpdateDeal = computed(() => crmPermissions.value.deals.can_update)
const canDeleteDeal = computed(() => crmPermissions.value.deals.can_delete)
const canViewContacts = computed(() => crmPermissions.value.contacts.can_view)
const canCreateContact = computed(() => crmPermissions.value.contacts.can_create)
const canUpdateContact = computed(() => crmPermissions.value.contacts.can_update)
const canDeleteContact = computed(() => crmPermissions.value.contacts.can_delete)
const canViewCompanies = computed(() => crmPermissions.value.companies.can_view)
const canCreateCompany = computed(() => crmPermissions.value.companies.can_create)
const canUpdateCompany = computed(() => crmPermissions.value.companies.can_update)
const canDeleteCompany = computed(() => crmPermissions.value.companies.can_delete)
const canAssignResponsible = computed(
  () =>
    canCreateDeal.value ||
    canUpdateDeal.value ||
    canCreateContact.value ||
    canUpdateContact.value ||
    canCreateCompany.value ||
    canUpdateCompany.value
)

const canManagePipelines = computed(() => ['owner', 'admin'].includes(authStore.role || ''))
const canManageTriggers = computed(() => ['owner', 'admin'].includes(authStore.role || ''))
const canUseTasks = computed(() => canViewDeals.value && ['owner', 'admin', 'manager'].includes(authStore.role || ''))
const canUseStats = computed(() => canViewDeals.value)
const hasAnyCrmAccess = computed(() => canViewAnyCrmEntity(crmPermissions.value))

const tabs = computed(() => {
  const next = []
  if (canViewDeals.value) next.push({ key: 'kanban', label: 'Kanban' })
  if (canViewContacts.value) next.push({ key: 'contacts', label: 'Контакты' })
  if (canViewCompanies.value) next.push({ key: 'companies', label: 'Компании' })
  if (canManagePipelines.value) next.push({ key: 'pipelines', label: 'Воронки' })
  if (canManageTriggers.value) next.push({ key: 'triggers', label: 'Триггеры' })
  if (canUseTasks.value) next.push({ key: 'tasks', label: 'Задачи' })
  if (canUseStats.value) next.push({ key: 'stats', label: 'Статистика' })
  return next
})
const tab = ref('kanban')

/* --- Pipelines --- */
const pipelines = ref<CrmPipeline[]>([])
const selectedPipeline = ref<number | null>(null)

/* --- Kanban --- */
const kanbanColumns = ref<KanbanColumn[]>([])
let dragDealId: number | null = null
const kanbanViewMode = ref<'board' | 'list'>('board')
const showKanbanFilters = ref(false)
const kanbanFilter = reactive({
  source: null as string | null,
  contact_id: null as number | null,
  company_id: null as number | null,
  date: null as string | null,
})
const dateFilterOptions = [
  { label: 'Сегодня', value: 'today' },
  { label: 'Вчера', value: 'yesterday' },
  { label: 'Неделя', value: 'week' },
]

const filteredKanbanColumns = computed(() => {
  const hasFilter = kanbanFilter.source || kanbanFilter.contact_id || kanbanFilter.company_id || kanbanFilter.date
  if (!hasFilter) return kanbanColumns.value
  const now = new Date()
  const todayStr = now.toISOString().slice(0, 10)
  const yesterdayStr = new Date(now.getTime() - 86400000).toISOString().slice(0, 10)
  const weekAgo = new Date(now.getTime() - 7 * 86400000)
  return kanbanColumns.value.map(col => ({
    ...col,
    deals: col.deals.filter(d => {
      if (kanbanFilter.source && (d as any).source !== kanbanFilter.source) return false
      if (kanbanFilter.contact_id && (d as any).contact_id !== kanbanFilter.contact_id) return false
      if (kanbanFilter.company_id && (d as any).company_id !== kanbanFilter.company_id) return false
      if (kanbanFilter.date && (d as any).created_at) {
        const created = (d as any).created_at.slice(0, 10)
        if (kanbanFilter.date === 'today' && created !== todayStr) return false
        if (kanbanFilter.date === 'yesterday' && created !== yesterdayStr) return false
        if (kanbanFilter.date === 'week' && new Date((d as any).created_at) < weekAgo) return false
      }
      return true
    }),
  }))
})

const flatDealsList = computed(() => {
  const result: Array<Record<string, unknown>> = []
  for (const col of filteredKanbanColumns.value) {
    for (const deal of col.deals) {
      result.push({ ...deal, stage_name: col.stage.name, _stage_color: col.stage.color })
    }
  }
  return result
})

const loadPipelines = async () => {
  if (!canViewDeals.value) {
    pipelines.value = []
    selectedPipeline.value = null
    return
  }
  pipelines.value = await crmApi.listPipelines()
  if (pipelines.value.length && !selectedPipeline.value) {
    selectedPipeline.value = pipelines.value[0].id
  }
}

const loadBoard = async () => {
  if (!canViewDeals.value || !selectedPipeline.value) return
  kanbanColumns.value = await crmApi.kanbanDeals(selectedPipeline.value)
}

const onDragStart = (e: DragEvent, dealId: number) => {
  dragDealId = dealId
  e.dataTransfer?.setData('text/plain', String(dealId))
}

const onDrop = async (_e: DragEvent, stageId: number) => {
  if (!canUpdateDeal.value || !dragDealId) return
  await crmApi.moveDeal(dragDealId, stageId)
  dragDealId = null
  await loadBoard()
}

/* --- Deal detail / edit --- */
const showDealDetail = ref(false)
const dealDetail = ref<(CrmDeal & { activities: CrmActivity[] }) | null>(null)
const dealEdit = reactive({
  name: '',
  amount: null as number | null,
  currency: 'RUB',
  contact_id: null as number | null,
  company_id: null as number | null,
  responsible_id: null as number | null,
  expected_close_date: '',
  source: '',
  loss_reason: '',
})
const newNote = ref('')
const newActivityType = ref('note')
const activityTypeOptions = [
  { label: '📝 Заметка', value: 'note' },
  { label: '📞 Звонок', value: 'call' },
  { label: '💬 Сообщение', value: 'message' },
  { label: '📧 Email', value: 'email' },
  { label: '✅ Задача', value: 'task' },
]
const activityTypeLabel = (type: string) => {
  const map: Record<string, string> = { call: 'Звонок', message: 'Сообщение', task: 'Задача', note: 'Заметка', email: 'Email', contract: 'Договор', stage_change: 'Смена стадии', system: 'Система' }
  return map[type] || type
}

const openDeal = async (id: number) => {
  dealDetail.value = await crmApi.getDeal(id)
  const d = dealDetail.value
  Object.assign(dealEdit, {
    name: d.name,
    amount: d.amount,
    currency: d.currency,
    contact_id: d.contact_id,
    company_id: (d as any).company_id ?? null,
    responsible_id: d.responsible_id,
    expected_close_date: (d as any).expected_close_date || '',
    source: (d as any).source || '',
    loss_reason: (d as any).loss_reason || '',
  })
  showDealDetail.value = true
}

const saveDealEdit = async () => {
  if (!canUpdateDeal.value || !dealDetail.value || !dealEdit.name) return
  await crmApi.patchDeal(dealDetail.value.id, {
    name: dealEdit.name,
    amount: dealEdit.amount,
    currency: dealEdit.currency,
    contact_id: dealEdit.contact_id,
    company_id: dealEdit.company_id,
    responsible_id: dealEdit.responsible_id,
    expected_close_date: dealEdit.expected_close_date || null,
    source: dealEdit.source,
    loss_reason: dealEdit.loss_reason,
  })
  showDealDetail.value = false
  await loadBoard()
}

const removeDeal = async () => {
  if (!canDeleteDeal.value || !dealDetail.value) return
  await crmApi.deleteDeal(dealDetail.value.id)
  showDealDetail.value = false
  await loadBoard()
}

const addNote = async () => {
  if (!canUpdateDeal.value || !dealDetail.value || !newNote.value.trim()) return
  await crmApi.createActivity({ activity_type: newActivityType.value, deal_id: dealDetail.value.id, title: newNote.value })
  newNote.value = ''
  newActivityType.value = 'note'
  dealDetail.value = await crmApi.getDeal(dealDetail.value.id)
}

const activityIcon = (type: string) => {
  const map: Record<string, string> = { call: '📞', message: '💬', task: '✅', note: '📝', email: '📧', contract: '📄', stage_change: '🔄', system: '⚙️' }
  return map[type] || '📌'
}

const contractStatusLabel = (s: string) => {
  const map: Record<string, string> = { draft: 'Черновик', sent: 'Отправлен', viewed: 'Просмотрен', signed: 'Подписан', expired: 'Истёк' }
  return map[s] || s
}

const downloadDealContractPdf = (contractId: number) => {
  const apiUrl = import.meta.env.VITE_API_URL || 'http://localhost:18100/api'
  const token = getAccessToken()
  const slug = getTenantSlug()
  window.open(`${apiUrl}/contracts/${contractId}/pdf/?token=${token}&tenant_slug=${slug}`, '_blank')
}

const showDealContractPreview = ref(false)
const dealContractPreviewHtml = ref('')

const previewDealContract = async (contractId: number) => {
  const data = await api<{ html_snapshot: string }>(`/contracts/${contractId}/`)
  dealContractPreviewHtml.value = data.html_snapshot
  showDealContractPreview.value = true
}

/* --- Signing flow in deal --- */
const showDealSigningDialog = ref(false)
const dealSigningContract = ref<Record<string, unknown> | null>(null)
const dealSigningRecipient = ref('')
const dealSigningUrl = ref('')
const dealSigningError = ref('')

const openDealSigningDialog = (contract: Record<string, unknown>) => {
  dealSigningContract.value = contract
  // Auto-fill phone from deal's contact
  const contactId = dealDetail.value?.contact_id
  const contact = contactId ? contacts.value.find((c: any) => c.id === contactId) : null
  dealSigningRecipient.value = contact?.phone || ''
  dealSigningUrl.value = (contract.signing_url as string) || ''
  dealSigningError.value = ''
  showDealSigningDialog.value = true
}

const dealSendForSigning = async () => {
  if (!dealSigningContract.value || !dealSigningRecipient.value) return
  dealSigningError.value = ''
  try {
    const result = await api<{ detail: string; token: string; signing_url: string }>(
      `/contracts/${dealSigningContract.value.id}/send-for-signing/`,
      { method: 'POST', body: { recipient: dealSigningRecipient.value } },
    )
    dealSigningUrl.value = result.signing_url
    if (dealDetail.value) {
      dealDetail.value = await crmApi.getDeal(dealDetail.value.id)
    }
  } catch (e: unknown) {
    const err = e as { data?: { detail?: string } }
    dealSigningError.value = err?.data?.detail || 'Ошибка отправки'
  }
}

const copyDealSigningLink = () => {
  navigator.clipboard.writeText(dealSigningUrl.value)
}

/* --- Create contract from deal --- */
const showDealContractDialog = ref(false)
const dealContractTemplateId = ref<number | null>(null)
const dealContractMethod = ref('sms_otp')
const contractTemplates = ref<Array<{ id: number; name: string }>>([])
const contractTemplateOptions = computed(() =>
  contractTemplates.value.map(t => ({ label: t.name, value: t.id }))
)

const openDealContract = async () => {
  await loadContractTemplates()
  dealContractTemplateId.value = null
  dealContractMethod.value = 'sms_otp'
  showDealContractDialog.value = true
}

const loadContractTemplates = async () => {
  if (contractTemplates.value.length === 0) {
    contractTemplates.value = await api<Array<{ id: number; name: string }>>('/contracts/templates/')
  }
}

const createDealContract = async () => {
  if (!dealDetail.value || !dealContractTemplateId.value) return
  await api('/contracts/generate', {
    method: 'POST',
    body: {
      template_id: dealContractTemplateId.value,
      deal_id: dealDetail.value.id,
      signing_method: dealContractMethod.value,
    },
  })
  showDealContractDialog.value = false
  dealDetail.value = await crmApi.getDeal(dealDetail.value.id)
}

/* --- New deal form --- */
const showDealForm = ref(false)
const dealForm = reactive({
  name: '',
  pipeline_id: null as number | null,
  stage_id: null as number | null,
  amount: null as number | null,
  currency: 'RUB',
  contact_id: null as number | null,
  company_id: null as number | null,
  responsible_id: null as number | null,
  expected_close_date: '',
  source: '',
})
const dealFormStages = ref<CrmStage[]>([])
const managers = ref<{ id: number; name: string }[]>([])

const dealFormStageOptions = computed(() =>
  dealFormStages.value.map(s => ({ label: s.name, value: s.id }))
)
const contactOptions = computed(() =>
  contacts.value.map(c => ({ label: `${c.first_name} ${c.last_name}`.trim(), value: c.id }))
)
const companyOptions = computed(() =>
  companies.value.map(c => ({ label: c.name, value: c.id }))
)
const managerOptions = computed(() =>
  managers.value.map(m => ({ label: m.name, value: m.id }))
)

const loadManagers = async () => {
  if (!canAssignResponsible.value) {
    managers.value = []
    return
  }
  managers.value = await crmApi.listManagers()
}

/* --- Quick-create inline --- */
const quickCreateTarget = ref('')
const showQuickContact = ref(false)
const showQuickCompany = ref(false)
const quickContact = reactive({ first_name: '', last_name: '', phone: '', email: '' })
const quickCompany = reactive({ name: '', inn: '', phone: '' })

const submitQuickContact = async () => {
  if (!canCreateContact.value || !quickContact.first_name) return
  try {
    const res = await crmApi.createContact({ ...quickContact })
    await loadContacts()
    if (quickCreateTarget.value === 'deal-contact') {
      dealForm.contact_id = res.id
    } else if (quickCreateTarget.value === 'edit-contact') {
      dealEdit.contact_id = res.id
    }
    showQuickContact.value = false
    Object.assign(quickContact, { first_name: '', last_name: '', phone: '', email: '' })
  } catch (e: any) {
    alert(e?.data?.detail || 'Ошибка создания контакта')
  }
}

const submitQuickCompany = async () => {
  if (!canCreateCompany.value || !quickCompany.name) return
  try {
    const res = await crmApi.createCompany({ ...quickCompany })
    await loadCompanies()
    if (quickCreateTarget.value === 'deal-company') {
      dealForm.company_id = res.id
    } else if (quickCreateTarget.value === 'contact-company') {
      contactForm.company_id = res.id
    } else if (quickCreateTarget.value === 'edit-company') {
      dealEdit.company_id = res.id
    }
    showQuickCompany.value = false
    Object.assign(quickCompany, { name: '', inn: '', phone: '' })
  } catch (e: any) {
    alert(e?.data?.detail || 'Ошибка создания компании')
  }
}

const onDealPipelineChange = async () => {
  dealForm.stage_id = null
  if (dealForm.pipeline_id) {
    dealFormStages.value = await crmApi.listStages(dealForm.pipeline_id)
  } else {
    dealFormStages.value = []
  }
}

const openDealForm = async () => {
  if (!canCreateDeal.value) return
  if (!dealForm.pipeline_id && selectedPipeline.value) {
    dealForm.pipeline_id = selectedPipeline.value
  }
  if (dealForm.pipeline_id) {
    dealFormStages.value = await crmApi.listStages(dealForm.pipeline_id)
  }
  showDealForm.value = true
}

const submitDeal = async () => {
  if (!canCreateDeal.value || !dealForm.name || !dealForm.pipeline_id) return
  let stageId = dealForm.stage_id
  if (!stageId) {
    const stages = dealFormStages.value.length ? dealFormStages.value : await crmApi.listStages(dealForm.pipeline_id)
    stageId = stages[0]?.id || null
  }
  if (!stageId) return
  await crmApi.createDeal({
    name: dealForm.name,
    pipeline_id: dealForm.pipeline_id,
    stage_id: stageId,
    amount: dealForm.amount,
    currency: dealForm.currency,
    contact_id: dealForm.contact_id,
    company_id: dealForm.company_id,
    responsible_id: dealForm.responsible_id,
    expected_close_date: dealForm.expected_close_date || null,
    source: dealForm.source,
  })
  showDealForm.value = false
  Object.assign(dealForm, { name: '', amount: null, currency: 'RUB', stage_id: null, contact_id: null, company_id: null, responsible_id: null, expected_close_date: '', source: '' })
  await loadBoard()
}

/* --- Contacts --- */
const contacts = ref<CrmContact[]>([])
const contactSearch = ref('')
const showContactForm = ref(false)
const contactForm = reactive({
  id: null as number | null,
  first_name: '',
  last_name: '',
  phone: '',
  email: '',
  position: '',
  company_id: null as number | null,
  messenger_id: '',
  source: '',
  responsible_id: null as number | null,
})

const loadContacts = async () => {
  if (!canViewContacts.value) {
    contacts.value = []
    return
  }
  contacts.value = await crmApi.listContacts(contactSearch.value || undefined)
}

/* --- Contact detail --- */
const showContactDetail = ref(false)
const contactDetail = ref<(CrmContact & { activities: CrmActivity[] }) | null>(null)

const openContact = async (id: number) => {
  contactDetail.value = await crmApi.getContact(id)
  showContactDetail.value = true
}

const editContact = (c: CrmContact) => {
  contactForm.id = c.id
  contactForm.first_name = c.first_name
  contactForm.last_name = c.last_name
  contactForm.phone = c.phone
  contactForm.email = c.email
  contactForm.position = (c as any).position || ''
  contactForm.company_id = c.company_id
  contactForm.messenger_id = (c as any).messenger_id || ''
  contactForm.source = (c as any).source || ''
  contactForm.responsible_id = c.responsible_id
  showContactForm.value = true
}

const submitContact = async () => {
  if (!contactForm.first_name) return
  if (contactForm.id ? !canUpdateContact.value : !canCreateContact.value) return
  const data = {
    first_name: contactForm.first_name,
    last_name: contactForm.last_name,
    phone: contactForm.phone,
    email: contactForm.email,
    position: contactForm.position,
    company_id: contactForm.company_id,
    messenger_id: contactForm.messenger_id,
    source: contactForm.source,
    responsible_id: contactForm.responsible_id,
  }
  if (contactForm.id) {
    await crmApi.patchContact(contactForm.id, data)
  } else {
    await crmApi.createContact(data)
  }
  showContactForm.value = false
  Object.assign(contactForm, { id: null, first_name: '', last_name: '', phone: '', email: '', position: '', company_id: null, messenger_id: '', source: '', responsible_id: null })
  await loadContacts()
}

const removeContact = async (id: number) => {
  if (!canDeleteContact.value) return
  await crmApi.deleteContact(id)
  await loadContacts()
}

/* --- Companies --- */
const companies = ref<CrmCompany[]>([])
const companySearch = ref('')
const showCompanyForm = ref(false)
const companyForm = reactive({ id: null as number | null, name: '', inn: '', phone: '', email: '' })

const loadCompanies = async () => {
  if (!canViewCompanies.value) {
    companies.value = []
    return
  }
  companies.value = await crmApi.listCompanies(companySearch.value || undefined)
}

const editCompany = (c: CrmCompany) => {
  companyForm.id = c.id
  companyForm.name = c.name
  companyForm.inn = c.inn
  companyForm.phone = c.phone
  companyForm.email = c.email
  showCompanyForm.value = true
}

const submitCompany = async () => {
  if (!companyForm.name) return
  if (companyForm.id ? !canUpdateCompany.value : !canCreateCompany.value) return
  if (companyForm.id) {
    await crmApi.patchCompany(companyForm.id, { name: companyForm.name, inn: companyForm.inn, phone: companyForm.phone, email: companyForm.email })
  } else {
    await crmApi.createCompany({ name: companyForm.name, inn: companyForm.inn, phone: companyForm.phone, email: companyForm.email })
  }
  showCompanyForm.value = false
  companyForm.id = null
  companyForm.name = ''
  companyForm.inn = ''
  companyForm.phone = ''
  companyForm.email = ''
  await loadCompanies()
}

const removeCompany = async (id: number) => {
  if (!canDeleteCompany.value) return
  await crmApi.deleteCompany(id)
  await loadCompanies()
}

/* --- Pipeline stages --- */
const selectedPipelineStages = ref<CrmStage[] | null>(null)
const selectedPipelineStagesFor = ref<number | null>(null)
const newStageName = ref('')
const showPipelineForm = ref(false)
const pipelineForm = reactive({ name: '' })

let dragStageIdx: number | null = null

const editPipelineStages = async (p: CrmPipeline) => {
  if (selectedPipelineStagesFor.value === p.id) {
    selectedPipelineStagesFor.value = null
    selectedPipelineStages.value = null
    return
  }
  selectedPipelineStages.value = await crmApi.listStages(p.id)
  selectedPipelineStagesFor.value = p.id
}

const addStage = async (pipelineId: number) => {
  if (!newStageName.value) return
  await crmApi.createStage(pipelineId, { name: newStageName.value })
  newStageName.value = ''
  selectedPipelineStages.value = await crmApi.listStages(pipelineId)
}

const removeStage = async (stageId: number, pipelineId: number) => {
  try {
    await crmApi.deleteStage(stageId)
    selectedPipelineStages.value = await crmApi.listStages(pipelineId)
  } catch (e: any) {
    alert(e?.data?.detail || 'Невозможно удалить этап (есть сделки)')
  }
}

const onStageDragStart = (e: DragEvent, idx: number) => {
  dragStageIdx = idx
  e.dataTransfer?.setData('text/plain', String(idx))
}

const onStageDrop = async (_e: DragEvent, targetIdx: number, pipelineId: number) => {
  if (dragStageIdx === null || dragStageIdx === targetIdx || !selectedPipelineStages.value) return
  const arr = [...selectedPipelineStages.value]
  const [moved] = arr.splice(dragStageIdx, 1)
  arr.splice(targetIdx, 0, moved)
  selectedPipelineStages.value = arr
  dragStageIdx = null
  await crmApi.reorderStages(pipelineId, arr.map(s => s.id))
}

const stageTypeLabel = (t: string) => {
  const map: Record<string, string> = { open: 'В работе', won: 'Успешно', lost: 'Проиграна' }
  return map[t] || t
}
const stageTypeSeverity = (t: string) => {
  const map: Record<string, string> = { open: 'info', won: 'success', lost: 'danger' }
  return (map[t] || 'secondary') as 'info' | 'success' | 'danger' | 'secondary'
}

/* --- Trigger config --- */
const showTriggerConfig = ref(false)
const triggerStage = ref<CrmStage | null>(null)
const triggerPipelineId = ref<number | null>(null)
const triggerStageId = ref<number | null>(null)
const triggerStagesList = ref<CrmStage[]>([])
const triggerForm = reactive({ type: '' as string, title: '', days_offset: 1, event: 'deal_stage_changed', template_id: null as number | null })
const triggerTypeOptions = [
  { label: 'Создать задачу', value: 'create_task' },
  { label: 'Отправить уведомление', value: 'send_notification' },
  { label: 'Создать договор', value: 'create_contract' },
]
const triggerTemplateOptions = computed(() =>
  contractTemplates.value.map(t => ({ label: t.name, value: t.id }))
)
const triggerStageOptions = computed(() =>
  triggerStagesList.value.map(s => ({ label: s.name, value: s.id }))
)

/* All triggers across all pipelines for the triggers tab */
const allPipelineStages = ref<Map<number, CrmStage[]>>(new Map())

const loadAllTriggers = async () => {
  if (!canManageTriggers.value) {
    allPipelineStages.value = new Map()
    return
  }
  await loadContractTemplates()
  const map = new Map<number, CrmStage[]>()
  for (const p of pipelines.value) {
    const stages = await crmApi.listStages(p.id)
    map.set(p.id, stages)
  }
  allPipelineStages.value = map
}

const allTriggers = computed(() => {
  const result: Array<{
    pipeline_id: number; pipeline_name: string; stage_id: number; stage_name: string;
    stage_color: string; action_type: string; action_label: string;
    action_title: string; action_days_offset: number; action_event: string;
    action_template_id: number | null; stage: CrmStage
  }> = []
  for (const p of pipelines.value) {
    const stages = allPipelineStages.value.get(p.id) || []
    for (const s of stages) {
      const a = s.auto_action as Record<string, unknown> | undefined
      if (a && a.type) {
        const opt = triggerTypeOptions.find(o => o.value === a.type)
        let label = opt?.label || String(a.type)
        const templateId = (a.template_id as number) || null
        if (a.type === 'create_contract' && templateId) {
          const tpl = contractTemplates.value.find(t => t.id === templateId)
          if (tpl) label += ` (${tpl.name})`
        }
        result.push({
          pipeline_id: p.id, pipeline_name: p.name,
          stage_id: s.id, stage_name: s.name, stage_color: s.color,
          action_type: a.type as string, action_label: label,
          action_title: (a.title as string) || '', action_days_offset: (a.days_offset as number) || 0,
          action_event: (a.event as string) || '', action_template_id: templateId, stage: s,
        })
      }
    }
  }
  return result
})

const triggerLabel = (s: CrmStage) => {
  const action = s.auto_action || {}
  const t = (action as any).type
  if (!t) return ''
  const map: Record<string, string> = { create_task: '📋 Задача', send_notification: '🔔 Уведомление', create_contract: '📄 Договор' }
  return map[t] || t
}

const onTriggerPipelineChange = async () => {
  triggerStageId.value = null
  if (triggerPipelineId.value) {
    triggerStagesList.value = await crmApi.listStages(triggerPipelineId.value)
  } else {
    triggerStagesList.value = []
  }
}

const openNewTrigger = () => {
  triggerStage.value = null
  triggerPipelineId.value = null
  triggerStageId.value = null
  triggerStagesList.value = []
  Object.assign(triggerForm, { type: '', title: 'Новая задача', days_offset: 1, event: 'deal_stage_changed', template_id: null })
  loadContractTemplates()
  showTriggerConfig.value = true
}

const editTrigger = (row: { stage: CrmStage }) => {
  const s = row.stage
  triggerStage.value = s
  triggerPipelineId.value = null
  triggerStageId.value = null
  const action = s.auto_action || {}
  triggerForm.type = (action as any).type || ''
  triggerForm.title = (action as any).title || 'Новая задача'
  triggerForm.days_offset = (action as any).days_offset ?? 1
  triggerForm.event = (action as any).event || 'deal_stage_changed'
  triggerForm.template_id = (action as any).template_id ?? null
  loadContractTemplates()
  showTriggerConfig.value = true
}

const deleteTrigger = async (row: { stage_id: number }) => {
  await crmApi.patchStage(row.stage_id, { auto_action: {} })
  await loadAllTriggers()
}

const openTriggerConfig = (s: CrmStage) => {
  triggerStage.value = s
  triggerPipelineId.value = null
  triggerStageId.value = null
  const action = s.auto_action || {}
  triggerForm.type = (action as any).type || ''
  triggerForm.title = (action as any).title || 'Новая задача'
  triggerForm.days_offset = (action as any).days_offset ?? 1
  triggerForm.event = (action as any).event || 'deal_stage_changed'
  triggerForm.template_id = (action as any).template_id ?? null
  loadContractTemplates()
  showTriggerConfig.value = true
}

const saveTrigger = async () => {
  const stageId = triggerStage.value?.id || triggerStageId.value
  if (!stageId || !triggerForm.type) return
  let auto_action: Record<string, unknown> = { type: triggerForm.type }
  if (triggerForm.type === 'create_task') {
    auto_action.title = triggerForm.title
    auto_action.days_offset = triggerForm.days_offset
  }
  if (triggerForm.type === 'send_notification') {
    auto_action.event = triggerForm.event
  }
  if (triggerForm.type === 'create_contract') {
    if (!triggerForm.template_id) return
    auto_action.template_id = triggerForm.template_id
  }
  await crmApi.patchStage(stageId, { auto_action })
  showTriggerConfig.value = false
  await loadAllTriggers()
  if (selectedPipelineStagesFor.value) {
    selectedPipelineStages.value = await crmApi.listStages(selectedPipelineStagesFor.value)
  }
}

const submitPipeline = async () => {
  if (!pipelineForm.name) return
  await crmApi.createPipeline({ name: pipelineForm.name })
  showPipelineForm.value = false
  pipelineForm.name = ''
  await loadPipelines()
}

const removePipeline = async (id: number) => {
  await crmApi.deletePipeline(id)
  await loadPipelines()
}

/* --- Tasks --- */
const tasksList = ref<Array<{ id: number; title: string; status: string; due_date: string | null; deal_id: number | null; created_at: string }>>([])
const tasksStatusFilter = ref<string | null>(null)
const showTaskDialog = ref(false)
const newTaskForm = reactive({ title: '', body: '', due_date: '' })
function resetTaskForm() {
  newTaskForm.title = ''
  newTaskForm.body = ''
  newTaskForm.due_date = ''
}
const createTask = async () => {
  if (!newTaskForm.title.trim()) return
  await crmApi.createActivity({
    activity_type: 'task',
    title: newTaskForm.title.trim(),
    body: newTaskForm.body.trim(),
    due_date: newTaskForm.due_date || null,
    status: 'planned',
  })
  showTaskDialog.value = false
  resetTaskForm()
  await loadTasks()
}
const taskStatusOptions = [
  { label: 'Запланировано', value: 'planned' },
  { label: 'Выполнено', value: 'done' },
  { label: 'Просрочено', value: 'overdue' },
]
const taskStatusLabel = (s: string) => {
  const map: Record<string, string> = { planned: 'Запланировано', done: 'Выполнено', overdue: 'Просрочено' }
  return map[s] || s
}
const taskStatusSeverity = (s: string) => {
  const map: Record<string, string> = { planned: 'info', done: 'success', overdue: 'danger' }
  return (map[s] || 'secondary') as 'info' | 'success' | 'danger' | 'secondary'
}
const loadTasks = async () => {
  if (!canUseTasks.value) {
    tasksList.value = []
    return
  }
  tasksList.value = await crmApi.myTasks(tasksStatusFilter.value || undefined)
}
const completeTask = async (id: number) => {
  await crmApi.patchActivity(id, { status: 'done' })
  await loadTasks()
}
const deleteTask = async (id: number) => {
  await crmApi.deleteActivity(id)
  await loadTasks()
}

/* --- Stats --- */
const statsPipelineId = ref<number | null>(null)
const pipelineStatsData = ref<Array<{ stage_name: string; total: number; amount: number }>>([])
const managerStatsData = ref<Array<{ manager_name: string | null; total: number; amount: number }>>([])
const pipelineTotal = computed(() => pipelineStatsData.value.reduce((sum, s) => sum + s.total, 0))

const loadStats = async () => {
  if (!canUseStats.value) {
    pipelineStatsData.value = []
    managerStatsData.value = []
    return
  }
  if (statsPipelineId.value) {
    pipelineStatsData.value = await crmApi.pipelineStats(statsPipelineId.value)
  }
  managerStatsData.value = await crmApi.managerStats()
}

/* --- Init --- */
onMounted(async () => {
  if (canViewDeals.value) {
    await loadPipelines()
  }

  await Promise.all([
    canViewDeals.value ? loadBoard() : Promise.resolve(),
    canViewContacts.value ? loadContacts() : Promise.resolve(),
    canViewCompanies.value ? loadCompanies() : Promise.resolve(),
    canAssignResponsible.value ? loadManagers() : Promise.resolve(),
    canManageTriggers.value ? loadAllTriggers() : Promise.resolve(),
  ])
})

watch(
  tabs,
  (items) => {
    if (!items.length) return
    if (!items.some(item => item.key === tab.value)) {
      tab.value = items[0].key
    }
  },
  { immediate: true }
)

watch(tab, (val) => {
  if (val === 'tasks' && canUseTasks.value) loadTasks()
  if (val === 'stats' && canUseStats.value) loadStats()
})
</script>

<style scoped>
.crm-gate {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.crm-gate :deep(> div) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.crm-section {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.tabs-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 14px;
}

.tab-btn {
  padding: 8px 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background: var(--p-surface-0);
  color: var(--p-text-color);
  cursor: pointer;
  font-size: 14px;
}

.tab-btn.active {
  background: var(--p-primary-color);
  color: var(--p-primary-contrast-color);
  border-color: var(--p-primary-color);
}

.tab-content {
  min-height: 400px;
  overflow: hidden;
}

.kanban-tab {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.toolbar {
  display: flex;
  gap: 8px;
  align-items: center;
  margin-bottom: 12px;
  flex-wrap: wrap;
  flex-shrink: 0;
}

.toolbar-select {
  min-width: 180px;
}

/* Kanban filters */
.kanban-filters {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.filter-field {
  min-width: 160px;
  max-width: 200px;
}

/* Kanban board */
.kanban {
  display: flex;
  gap: 12px;
  overflow-x: auto;
  padding-bottom: 12px;
  max-width: 100%;
  flex: 1;
  min-height: 0;
}

.kanban-col {
  min-width: 220px;
  max-width: 280px;
  flex: 0 0 auto;
  padding: 10px;
  display: flex;
  flex-direction: column;
}

.kanban-col header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  flex-shrink: 0;
}

.kanban-col-body {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.stage-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  display: inline-block;
  flex-shrink: 0;
}

.badge-count {
  margin-left: auto;
  background: var(--p-surface-100);
  border-radius: 999px;
  padding: 2px 8px;
  font-size: 12px;
}

.deal-card {
  padding: 10px;
  margin-bottom: 8px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  cursor: grab;
  transition: box-shadow 0.15s;
}

.deal-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
}

.deal-name {
  font-weight: 600;
  font-size: 14px;
}

.deal-amount {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

/* Kanban list view */
.kanban-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
}

.list-stage-group {
  margin-bottom: 16px;
}

.list-stage-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 2px solid var(--p-content-border-color);
  margin-bottom: 4px;
}

.deal-link {
  color: var(--p-primary-color);
  cursor: pointer;
  font-weight: 500;
}

.deal-link:hover {
  text-decoration: underline;
}

/* Deal contracts section */
.deal-contracts-section h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.deal-contract-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 13px;
}

.deal-contract-name {
  flex: 1;
}

.deal-contract-date {
  color: var(--text-muted);
  font-size: 12px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: 600;
}

.status-draft { background: var(--p-surface-100); color: var(--p-text-color); }
.status-sent { background: #dbeafe; color: #1d4ed8; }
.status-viewed { background: #fef3c7; color: #92400e; }
.status-signed { background: #dcfce7; color: #16a34a; }
.status-expired { background: #fee2e2; color: #991b1b; }

/* Activity section in deal dialog */
.activity-section {
  max-height: 320px;
  display: flex;
  flex-direction: column;
}

.activity-section h4 {
  margin: 0 0 8px;
  flex-shrink: 0;
}

.activity-list {
  flex: 1;
  overflow-y: auto;
  min-height: 0;
  max-height: 220px;
  margin-bottom: 8px;
}

.add-activity-row {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.activity-type-select {
  width: 150px;
  flex-shrink: 0;
}

/* Timeline */
.timeline-item {
  display: flex;
  gap: 10px;
  align-items: flex-start;
  padding: 8px 0;
  border-bottom: 1px solid var(--p-content-border-color);
}

.tl-icon {
  font-size: 18px;
  min-width: 24px;
  text-align: center;
}

.tl-content {
  flex: 1;
  min-width: 0;
}

.tl-body {
  font-size: 13px;
  color: var(--text-muted);
  margin-top: 2px;
}

.tl-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
}

.tl-date {
  font-size: 12px;
  color: var(--text-muted);
}

/* Pipeline stages - draggable */
.stage-row-draggable {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 6px;
  margin-bottom: 4px;
  cursor: grab;
  background: var(--p-surface-0);
  transition: background 0.15s;
}

.stage-row-draggable:hover {
  background: var(--p-surface-50);
}

.stage-drag-handle {
  cursor: grab;
  color: var(--text-muted);
  font-size: 16px;
  user-select: none;
}

.stage-name-text {
  flex: 1;
  font-size: 14px;
}

.stage-type-tag {
  font-size: 11px;
}

/* Form */
.form-grid {
  display: grid;
  gap: 10px;
}

.form-row-2 {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.field-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 4px;
  color: var(--p-text-color);
}

.w-full {
  width: 100%;
}

.flex-1 {
  flex: 1;
  min-width: 0;
}

.select-with-add {
  display: flex;
  gap: 4px;
  align-items: flex-start;
}

.empty-state {
  color: var(--text-muted);
  padding: 24px;
  text-align: center;
}

.stats-section {
  margin-bottom: 20px;
}

.stats-section h4 {
  margin: 0 0 8px;
}
</style>

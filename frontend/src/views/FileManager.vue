<template>
  <v-container fluid>
    <!-- 경로 + 액션 바 -->
    <v-card flat class="mb-4 pa-3">
      <div class="d-flex align-center flex-wrap">
        <v-btn variant="text" size="small" @click="goBack" :disabled="currentPath === '/'" class="mr-1">
          <v-icon>mdi-arrow-left</v-icon>
        </v-btn>
        <v-breadcrumbs :items="breadcrumbs" density="compact" class="pa-0">
          <template v-slot:item="{ item }">
            <v-breadcrumbs-item @click="navigateTo(item.path)" :disabled="item.disabled"
              style="cursor: pointer;">{{ item.title }}</v-breadcrumbs-item>
          </template>
        </v-breadcrumbs>
        <v-spacer />
        <v-btn icon="mdi-refresh" variant="text" @click="loadFiles" :loading="loading" size="small" />
        <v-btn icon="mdi-folder-plus" variant="text" @click="showNewFolderDialog = true" size="small" />
        <v-btn icon="mdi-upload" variant="text" @click="$refs.fileInput.click()" size="small" />
        <input ref="fileInput" type="file" multiple hidden @change="handleFileUpload" />
      </div>
    </v-card>

    <!-- 파일 목록 테이블 -->
    <v-card>
      <v-table hover density="compact">
        <thead>
          <tr>
            <th style="width:40px"></th>
            <th>이름</th>
            <th style="width:100px">크기</th>
            <th style="width:180px">수정일</th>
            <th style="width:120px"></th>
          </tr>
        </thead>
        <tbody>
          <tr v-if="loading"><td colspan="5" class="text-center pa-8"><v-progress-circular indeterminate /></td></tr>
          <tr v-else-if="!files.length"><td colspan="5" class="text-center pa-8 text-grey">빈 디렉토리</td></tr>
          <tr v-for="f in files" :key="f.path"
            @click="f.is_dir ? navigateTo(f.path) : null"
            :style="f.is_dir ? 'cursor:pointer' : ''">
            <td><v-icon :color="iconOf(f).color" size="small">{{ iconOf(f).icon }}</v-icon></td>
            <td><span :class="f.is_dir ? 'font-weight-medium' : ''">{{ f.name }}</span></td>
            <td class="text-grey">{{ f.size_display }}</td>
            <td class="text-grey text-caption">{{ f.modified }}</td>
            <td class="text-right">
              <v-btn v-if="canEdit(f)" icon="mdi-pencil" size="x-small" variant="text" @click.stop="editFile(f)" />
              <v-btn v-if="!f.is_dir" icon="mdi-download" size="x-small" variant="text" @click.stop="downloadIt(f)" />
              <v-menu>
                <template v-slot:activator="{ props }">
                  <v-btn icon="mdi-dots-vertical" size="x-small" variant="text" v-bind="props" @click.stop />
                </template>
                <v-list density="compact">
                  <v-list-item @click="startRename(f)"><v-list-item-title>이름 변경</v-list-item-title></v-list-item>
                  <v-list-item @click="confirmDelete(f)" class="text-red"><v-list-item-title>삭제</v-list-item-title></v-list-item>
                </v-list>
              </v-menu>
            </td>
          </tr>
        </tbody>
      </v-table>
    </v-card>

    <!-- 드래그 오버레이 -->
    <div v-if="dragging" class="drop-zone" @dragover.prevent @dragleave="dragging=false" @drop="dropUpload">
      <v-icon size="64" color="primary">mdi-cloud-upload</v-icon>
      <p class="text-h6 mt-4">파일을 놓아서 업로드</p>
    </div>

    <!-- 에디터 (줄번호 포함) -->
    <v-dialog v-model="showEditor" max-width="960" persistent>
      <v-card style="background:#1e1e2e;">
        <v-card-title class="d-flex align-center" style="background:#181825;color:#cdd6f4;">
          <v-icon class="mr-2" color="blue-lighten-2">mdi-file-document-edit</v-icon>
          <span>{{ editingFile?.name }}</span>
          <v-chip size="x-small" variant="tonal" class="ml-3" color="grey">
            {{ editorLineCount }}줄
          </v-chip>
          <v-spacer />
          <v-chip size="x-small" variant="tonal" color="blue-grey" class="mr-2">
            줄 {{ cursorLine }}, 칸 {{ cursorCol }}
          </v-chip>
          <v-btn icon="mdi-close" variant="text" size="small" @click="showEditor=false" />
        </v-card-title>
        <v-card-text class="pa-0">
          <div class="editor-wrap" ref="editorWrap">
            <div class="line-numbers" ref="lineNumbers">
              <div v-for="n in editorLineCount" :key="n" class="line-num"
                :class="{ 'line-num-active': n === cursorLine }">{{ n }}</div>
            </div>
            <textarea ref="editorArea" v-model="editorContent" class="code-area"
              spellcheck="false" wrap="off"
              @scroll="syncScroll" @keyup="updateCursor" @click="updateCursor"
              @keydown.tab.prevent="insertTab" />
          </div>
        </v-card-text>
        <v-card-actions style="background:#181825;">
          <v-spacer />
          <v-btn variant="text" @click="showEditor=false">취소</v-btn>
          <v-btn color="primary" variant="elevated" :loading="saving" @click="saveFile">
            <v-icon start size="16">mdi-content-save</v-icon> 저장
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 새폴더/이름변경/삭제 다이얼로그 -->
    <v-dialog v-model="showNewFolderDialog" max-width="400">
      <v-card><v-card-title>새 폴더</v-card-title>
        <v-card-text><v-text-field v-model="newFolderName" label="폴더명" @keyup.enter="createFolder" autofocus /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="showNewFolderDialog=false">취소</v-btn><v-btn color="primary" @click="createFolder">생성</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showRenameDialog" max-width="400">
      <v-card><v-card-title>이름 변경</v-card-title>
        <v-card-text><v-text-field v-model="renameName" :label="renamingFile?.name" @keyup.enter="doRename" autofocus /></v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="showRenameDialog=false">취소</v-btn><v-btn color="primary" @click="doRename">변경</v-btn></v-card-actions>
      </v-card>
    </v-dialog>
    <v-dialog v-model="showDeleteConfirm" max-width="400">
      <v-card><v-card-title class="text-red">삭제 확인</v-card-title>
        <v-card-text><strong>{{ deletingFile?.name }}</strong> 삭제하시겠습니까?
          <p v-if="deletingFile?.is_dir" class="text-red mt-2">⚠️ 내부 파일 모두 삭제됩니다!</p>
        </v-card-text>
        <v-card-actions><v-spacer /><v-btn @click="showDeleteConfirm=false">취소</v-btn><v-btn color="red" @click="doDelete">삭제</v-btn></v-card-actions>
      </v-card>
    </v-dialog>

    <v-snackbar v-model="snack" :color="snackColor" timeout="3000">{{ snackMsg }}</v-snackbar>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import api from '../api'

const route = useRoute()
const cn = computed(() => route.params.name)
const files = ref([])
const currentPath = ref('/')
const loading = ref(false)
const dragging = ref(false)
const showEditor = ref(false)
const editingFile = ref(null)
const editorContent = ref('')
const saving = ref(false)
const editorWrap = ref(null)
const lineNumbers = ref(null)
const editorArea = ref(null)
const cursorLine = ref(1)
const cursorCol = ref(1)

const editorLineCount = computed(() => {
  if (!editorContent.value) return 1
  return editorContent.value.split('\n').length
})
const showNewFolderDialog = ref(false)
const newFolderName = ref('')
const showRenameDialog = ref(false)
const renamingFile = ref(null)
const renameName = ref('')
const showDeleteConfirm = ref(false)
const deletingFile = ref(null)
const snack = ref(false)
const snackMsg = ref('')
const snackColor = ref('success')

const EDIT_EXT = ['.txt','.cfg','.conf','.ini','.properties','.json','.yml','.yaml','.xml','.toml','.env','.sh','.bat','.log','.md','.csv']

const breadcrumbs = computed(() => {
  const parts = currentPath.value.split('/').filter(Boolean)
  const items = [{ title: '/', path: '/', disabled: false }]
  let acc = ''
  for (const p of parts) { acc += '/' + p; items.push({ title: p, path: acc, disabled: false }) }
  if (items.length) items[items.length-1].disabled = true
  return items
})

function iconOf(f) {
  if (f.is_dir) return { icon: 'mdi-folder', color: 'amber' }
  const ext = f.name.includes('.') ? f.name.split('.').pop().toLowerCase() : ''
  const m = { jar:'red', dll:'purple', pak:'teal', zip:'orange', gz:'orange', log:'grey', json:'yellow-darken-2', yml:'pink', yaml:'pink', properties:'green', cfg:'green', conf:'green', sh:'green-lighten-1' }
  const ic = { jar:'mdi-language-java', dll:'mdi-cog', pak:'mdi-package-variant', zip:'mdi-folder-zip', gz:'mdi-folder-zip', log:'mdi-text-long', json:'mdi-code-json', yml:'mdi-file-cog', yaml:'mdi-file-cog', properties:'mdi-file-cog', cfg:'mdi-file-cog', sh:'mdi-console' }
  return { icon: ic[ext] || 'mdi-file', color: m[ext] || 'grey' }
}
function canEdit(f) { return !f.is_dir && EDIT_EXT.some(e => f.name.toLowerCase().endsWith(e)) }

async function loadFiles() {
  loading.value = true
  try { files.value = (await api.get(`/api/containers/${cn.value}/files`, { params: { path: currentPath.value } })).data.files }
  catch(e) { notify(e.response?.data?.detail || '조회 실패', 'error') }
  finally { loading.value = false }
}
function navigateTo(p) { currentPath.value = p; loadFiles() }
function goBack() { const parts = currentPath.value.split('/').filter(Boolean); parts.pop(); currentPath.value = '/' + parts.join('/'); loadFiles() }

async function editFile(f) {
  try { const r = await api.get(`/api/containers/${cn.value}/files/read`, { params: { path: f.path } }); editingFile.value = f; editorContent.value = r.data.content; showEditor.value = true }
  catch(e) { notify(e.response?.data?.detail || '읽기 실패', 'error') }
}
async function saveFile() {
  saving.value = true
  try { await api.put(`/api/containers/${cn.value}/files/write`, { path: editingFile.value.path, content: editorContent.value }); notify('저장됨'); showEditor.value = false }
  catch(e) { notify(e.response?.data?.detail || '저장 실패', 'error') }
  finally { saving.value = false }
}
function downloadIt(f) { window.open(`/api/containers/${cn.value}/files/download?path=${encodeURIComponent(f.path)}`, '_blank') }

async function handleFileUpload(e) {
  for (const file of e.target.files) { await doUp(file) }
  loadFiles(); e.target.value = ''
}
async function doUp(file) {
  const fd = new FormData(); fd.append('file', file)
  try { await api.post(`/api/containers/${cn.value}/files/upload?dest_dir=${encodeURIComponent(currentPath.value)}`, fd); notify(`${file.name} 업로드 완료`) }
  catch(e) { notify(`${file.name} 실패`, 'error') }
}
function dropUpload(e) { e.preventDefault(); dragging.value = false; const fs = e.dataTransfer?.files; if(!fs?.length) return; (async()=>{ for(const f of fs) await doUp(f); loadFiles() })() }

async function createFolder() {
  if(!newFolderName.value) return
  try { await api.post(`/api/containers/${cn.value}/files/mkdir`, { path: (currentPath.value === '/' ? '/' : currentPath.value+'/') + newFolderName.value }); notify('폴더 생성됨'); showNewFolderDialog.value=false; newFolderName.value=''; loadFiles() }
  catch(e) { notify(e.response?.data?.detail || '실패', 'error') }
}
function startRename(f) { renamingFile.value=f; renameName.value=f.name; showRenameDialog.value=true }
async function doRename() {
  try { await api.put(`/api/containers/${cn.value}/files/rename`, { old_path: renamingFile.value.path, new_name: renameName.value }); notify('변경됨'); showRenameDialog.value=false; loadFiles() }
  catch(e) { notify(e.response?.data?.detail||'실패','error') }
}
function confirmDelete(f) { deletingFile.value=f; showDeleteConfirm.value=true }
async function doDelete() {
  try { await api.delete(`/api/containers/${cn.value}/files/delete`, { params:{ path: deletingFile.value.path } }); notify('삭제됨'); showDeleteConfirm.value=false; loadFiles() }
  catch(e) { notify(e.response?.data?.detail||'실패','error') }
}

function notify(m, c='success') { snackMsg.value=m; snackColor.value=c; snack.value=true }

function syncScroll() {
  if (lineNumbers.value && editorArea.value) {
    lineNumbers.value.scrollTop = editorArea.value.scrollTop
  }
}
function updateCursor() {
  if (!editorArea.value) return
  const pos = editorArea.value.selectionStart
  const text = editorContent.value.substring(0, pos)
  const lines = text.split('\n')
  cursorLine.value = lines.length
  cursorCol.value = lines[lines.length - 1].length + 1
}
function insertTab(e) {
  const ta = editorArea.value
  const start = ta.selectionStart
  const end = ta.selectionEnd
  editorContent.value = editorContent.value.substring(0, start) + '  ' + editorContent.value.substring(end)
  nextTick(() => { ta.selectionStart = ta.selectionEnd = start + 2 })
}
if(typeof window!=='undefined') window.addEventListener('dragenter', ()=>{ dragging.value=true })
onMounted(loadFiles)
watch(cn, loadFiles)
</script>

<style scoped>
.drop-zone { position:fixed; inset:0; background:rgba(0,0,0,.7); display:flex; flex-direction:column; align-items:center; justify-content:center; z-index:9999 }

.editor-wrap {
  display: flex;
  height: 520px;
  background: #1e1e2e;
  font-family: 'Consolas', 'Fira Code', 'D2Coding', monospace;
  font-size: 13px;
  line-height: 1.5;
}
.line-numbers {
  width: 56px;
  min-width: 56px;
  padding: 12px 0;
  background: #181825;
  border-right: 1px solid #313244;
  overflow: hidden;
  user-select: none;
}
.line-num {
  padding: 0 12px 0 0;
  text-align: right;
  color: #585b70;
  height: 19.5px;
}
.line-num-active {
  color: #cdd6f4;
  background: rgba(88, 166, 255, 0.06);
}
.code-area {
  flex: 1;
  padding: 12px;
  background: transparent;
  color: #cdd6f4;
  border: none;
  outline: none;
  resize: none;
  overflow: auto;
  white-space: pre;
  font-family: inherit;
  font-size: inherit;
  line-height: inherit;
  tab-size: 2;
}
.code-area::-webkit-scrollbar { width: 8px; height: 8px; }
.code-area::-webkit-scrollbar-thumb { background: #45475a; border-radius: 4px; }
.code-area::-webkit-scrollbar-track { background: transparent; }
</style>

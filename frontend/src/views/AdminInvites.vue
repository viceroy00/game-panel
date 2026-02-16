<template>
  <v-container>
    <div class="d-flex align-center mb-4">
      <h2 class="font-weight-bold" style="color:#E6EDF3;">🎟️ 초대 코드 관리</h2>
      <v-spacer />
      <v-btn color="primary" @click="showCreate = true"><v-icon start>mdi-plus</v-icon>코드 생성</v-btn>
    </div>

    <v-card style="border:1px solid rgba(88,166,255,0.15);">
    <v-table class="bg-transparent">
      <thead>
        <tr>
          <th style="color:#8B949E;">코드</th>
          <th style="color:#8B949E;">메모</th>
          <th style="color:#8B949E;">사용</th>
          <th style="color:#8B949E;">만료</th>
          <th style="color:#8B949E;">상태</th>
          <th></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="c in codes" :key="c.id">
          <td style="font-family:monospace;font-size:1.1em;letter-spacing:1px">
            {{ c.code }}
            <v-btn icon="mdi-content-copy" size="x-small" variant="text" color="primary"
              @click="navigator.clipboard.writeText(c.code)" />
          </td>
          <td style="color:#8B949E;">{{ c.note || '-' }}</td>
          <td>{{ c.use_count }} / {{ c.max_uses }}</td>
          <td class="text-caption" style="color:#8B949E;">{{ c.expires_at ? new Date(c.expires_at).toLocaleString('ko-KR') : '무제한' }}</td>
          <td>
            <v-chip :color="c.is_active ? 'success' : 'default'" size="small" variant="tonal">
              {{ c.is_active ? '활성' : '비활성' }}
            </v-chip>
          </td>
          <td>
            <v-btn v-if="c.is_active" icon="mdi-close" size="small" variant="text" color="error"
              @click="deactivate(c.id)" title="비활성화" />
          </td>
        </tr>
        <tr v-if="!codes.length">
          <td colspan="6" class="text-center pa-8" style="color:#8B949E;">생성된 초대 코드가 없습니다</td>
        </tr>
      </tbody>
    </v-table>
    </v-card>

    <!-- 생성 다이얼로그 -->
    <v-dialog v-model="showCreate" max-width="400">
      <v-card style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title style="color:#E6EDF3;">초대 코드 생성</v-card-title>
        <v-card-text>
          <v-text-field v-model="newNote" label="메모 (누구한테 줄 코드인지)" placeholder="김OO" />
          <v-select v-model="newMaxUses" :items="[1,2,3,5,10]" label="최대 사용 횟수" />
          <v-select v-model="newExpires" :items="expireOptions" item-title="text" item-value="value"
            label="유효 기간" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn variant="text" color="primary" @click="showCreate=false">취소</v-btn>
          <v-btn color="primary" :loading="creating" @click="create">생성</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- 생성 결과 -->
    <v-dialog v-model="showResult" max-width="400">
      <v-card style="border:1px solid rgba(88,166,255,0.15);">
        <v-card-title class="text-center" style="color:#E6EDF3;">✅ 코드 생성 완료</v-card-title>
        <v-card-text class="text-center">
          <v-chip color="primary" size="x-large" variant="elevated"
            style="font-family:monospace;font-size:1.3em;letter-spacing:3px">
            {{ createdCode }}
          </v-chip>
          <p class="mt-4" style="color:#8B949E;">지인에게 이 코드를 전달하세요</p>
          <v-btn block variant="outlined" color="primary" class="mt-2"
            @click="navigator.clipboard.writeText(createdCode)">
            <v-icon start>mdi-content-copy</v-icon>복사
          </v-btn>
        </v-card-text>
        <v-card-actions>
          <v-spacer /><v-btn variant="text" color="primary" @click="showResult=false">닫기</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '../api'

const codes = ref([])
const showCreate = ref(false)
const showResult = ref(false)
const createdCode = ref('')
const creating = ref(false)
const newNote = ref('')
const newMaxUses = ref(1)
const newExpires = ref(72)

const expireOptions = [
  { text: '24시간', value: 24 },
  { text: '3일', value: 72 },
  { text: '7일', value: 168 },
  { text: '30일', value: 720 },
]

async function load() {
  try { codes.value = (await api.get('/api/invite/codes')).data } catch {}
}

async function create() {
  creating.value = true
  try {
    const r = await api.post('/api/invite/codes', {
      note: newNote.value || null,
      max_uses: newMaxUses.value,
      expires_hours: newExpires.value,
    })
    createdCode.value = r.data.code
    showCreate.value = false
    showResult.value = true
    newNote.value = ''
    load()
  } catch {}
  finally { creating.value = false }
}

async function deactivate(id) {
  try { await api.delete(`/api/invite/codes/${id}`); load() } catch {}
}

onMounted(load)
</script>

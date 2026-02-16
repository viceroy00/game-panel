<template>
  <v-container class="fill-height" fluid>
    <v-row justify="center" align="center">
      <v-col cols="12" sm="8" md="5" lg="4">

        <!-- ═══ 로그인 / 가입 탭 ═══ -->
        <v-card v-if="step === 'login'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <div class="text-center mb-2">
            <span style="font-size:2.5em">🎮</span>
          </div>
          <v-card-title class="text-center text-h5 font-weight-bold" style="color:#58A6FF;">Game Panel</v-card-title>
          <v-card-subtitle class="text-center mb-6" style="color:#8B949E;">비공개 게임 서버 관리</v-card-subtitle>

          <v-card-text>
            <!-- Discord 로그인 -->
            <v-btn block size="large" class="mb-5" @click="discordLogin"
              style="background:#5865F2; color:white;">
              <v-icon start>mdi-discord</v-icon> Discord로 로그인
            </v-btn>

            <div class="d-flex align-center mb-5">
              <v-divider /><span class="text-caption mx-3" style="color:#484F58;">또는</span><v-divider />
            </div>

            <!-- ID/PW 로그인 -->
            <v-text-field v-model="username" label="사용자명" prepend-inner-icon="mdi-account"
              @keyup.enter="login" class="mb-1" />
            <v-text-field v-model="password" label="비밀번호" type="password"
              prepend-inner-icon="mdi-lock" @keyup.enter="login" class="mb-2" />
            <v-btn block color="primary" size="large" :loading="loading" @click="login">
              로그인
            </v-btn>

            <div class="text-center mt-4">
              <v-btn variant="text" color="primary" @click="step = 'invite'">
                초대 코드로 가입
              </v-btn>
              <v-btn variant="text" color="primary" @click="step = 'forgot-pw'">
                비밀번호 찾기
              </v-btn>
            </div>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 초대 코드 가입 ═══ -->
        <v-card v-else-if="step === 'invite'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">🎟️ 초대 코드 가입</v-card-title>
          <v-card-text>
            <v-text-field v-model="inviteCode" label="초대 코드" prepend-icon="mdi-ticket"
              placeholder="XXXXXXXXXXXX" style="font-family:monospace" />

            <template v-if="inviteVerified">
              <v-alert type="success" variant="tonal" class="mb-4">유효한 코드입니다!</v-alert>
              <v-text-field v-model="username" label="사용자명" prepend-icon="mdi-account" />
              <v-text-field v-model="password" label="비밀번호 (8자 이상)" type="password"
                prepend-icon="mdi-lock" />
              <v-text-field v-model="displayName" label="표시 이름 (선택)" prepend-icon="mdi-badge-account" />
              <v-btn block color="primary" size="large" :loading="loading" @click="registerInvite">
                가입하기
              </v-btn>
            </template>
            <template v-else>
              <v-btn block color="primary" size="large" :loading="loading" @click="verifyInvite">코드 확인</v-btn>
            </template>

            <v-btn block variant="text" color="primary" @click="step = 'login'" class="mt-2">돌아가기</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 2FA 코드 입력 ═══ -->
        <v-card v-else-if="step === '2fa'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">🔐 2차 인증</v-card-title>
          <v-card-text>
            <p class="text-center mb-4">Authenticator 앱의 6자리 코드를 입력하세요</p>
            <v-otp-input v-model="totpCode" length="6" @finish="verify2fa" />
            <v-btn block color="primary" size="large" :loading="loading" @click="verify2fa" class="mt-4">인증</v-btn>
            <v-divider class="my-4" />
            <v-btn block variant="text" color="primary" @click="step = 'recovery'">복구 코드로 로그인</v-btn>
            <v-btn block variant="text" color="primary" @click="send2faRecovery">📧 이메일로 2FA 복구</v-btn>
            <v-btn block variant="text" color="primary" @click="step = 'login'">돌아가기</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 복구 코드 입력 ═══ -->
        <v-card v-else-if="step === 'recovery'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">🔑 복구 코드</v-card-title>
          <v-card-text>
            <v-text-field v-model="recoveryCode" label="8자리 복구 코드" maxlength="8"
              placeholder="A1B2C3D4" style="font-family:monospace;font-size:1.2em"
              @keyup.enter="verifyRecovery" />
            <v-btn block color="primary" size="large" :loading="loading" @click="verifyRecovery">인증</v-btn>
            <v-btn block variant="text" color="primary" @click="step='2fa'" class="mt-2">TOTP로 돌아가기</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 2FA 이메일 복구 ═══ -->
        <v-card v-else-if="step === '2fa-email-recovery'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">📧 2FA 이메일 복구</v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              등록된 이메일로 복구 코드가 발송되었습니다.<br>
              <span v-if="maskedEmail" style="color:#58A6FF;">{{ maskedEmail }}</span>
            </v-alert>
            <v-otp-input v-model="emailRecoveryCode" length="6" @finish="confirm2faRecovery" />
            <v-btn block color="primary" size="large" :loading="loading" @click="confirm2faRecovery" class="mt-4">확인</v-btn>
            <v-btn block variant="text" color="primary" @click="step = '2fa'" class="mt-2">돌아가기</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ QR 코드 설정 ═══ -->
        <v-card v-else-if="step === 'setup-qr'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">📱 2차 인증 설정</v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              보안을 위해 2차 인증이 필요합니다.<br>Google Authenticator 등으로 QR 코드를 스캔하세요.
            </v-alert>
            <div class="text-center mb-4">
              <img v-if="qrBase64" :src="'data:image/png;base64,'+qrBase64" style="max-width:200px;border-radius:8px" />
            </div>
            <v-expansion-panels variant="accordion" class="mb-4">
              <v-expansion-panel title="QR 스캔이 안 되나요?">
                <v-expansion-panel-text>
                  <p class="mb-2">아래 코드를 수동 입력:</p>
                  <v-text-field :model-value="totpSecret" readonly variant="outlined"
                    append-inner-icon="mdi-content-copy"
                    @click:append-inner="navigator.clipboard.writeText(totpSecret)"
                    style="font-family:monospace" />
                </v-expansion-panel-text>
              </v-expansion-panel>
            </v-expansion-panels>
            <p class="text-center mb-4">앱에 표시된 6자리 코드 입력</p>
            <v-otp-input v-model="totpCode" length="6" @finish="activateTotp" />
            <v-btn block color="primary" size="large" :loading="loading" @click="activateTotp" class="mt-4">활성화</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 복구 코드 표출 ═══ -->
        <v-card v-else-if="step === 'show-recovery'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center text-h5 font-weight-bold" style="color:#58A6FF;">
            🔑 긴급 복구 코드
          </v-card-title>
          <v-card-text>
            <v-alert color="warning" variant="tonal" class="mb-4" prominent>
              <strong>⚠️ 절대 잃어버리지 마세요!</strong><br>
              이 코드는 지금만 볼 수 있으며, 다시 표시되지 않습니다.
            </v-alert>
            <v-sheet style="background:rgba(88,166,255,0.08); border:1px solid rgba(88,166,255,0.2);" class="pa-4 rounded-lg mb-4">
              <div class="d-flex flex-wrap justify-center" style="gap:8px">
                <v-chip v-for="(c,i) in recoveryCodes" :key="i" color="primary" variant="elevated"
                  size="large" style="font-family:monospace;font-size:1.1em;letter-spacing:2px">{{ c }}</v-chip>
              </div>
            </v-sheet>
            <v-row dense class="mb-4">
              <v-col cols="6">
                <v-btn variant="outlined" color="primary" block size="large"
                  @click="navigator.clipboard.writeText(recoveryCodes.join('\n'))">
                  <v-icon start>mdi-content-copy</v-icon>복사
                </v-btn>
              </v-col>
              <v-col cols="6">
                <v-btn variant="outlined" color="primary" block size="large" @click="dlRecovery">
                  <v-icon start>mdi-download</v-icon>다운로드
                </v-btn>
              </v-col>
            </v-row>
            <v-checkbox v-model="recoveryConfirmed" color="primary" label="안전한 곳에 저장했습니다" />
            <v-btn block color="primary" size="large" :disabled="!recoveryConfirmed" @click="finishSetup">
              설정 완료 — 다음 단계
            </v-btn>
          </v-card-text>
        </v-card>

        <!-- ═══ 이메일 인증 ═══ -->
        <v-card v-else-if="step === 'email-verify'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">📧 이메일 인증</v-card-title>
          <v-card-text>
            <v-alert type="info" variant="tonal" class="mb-4">
              이메일 주소를 등록하고 인증하면 비밀번호 재설정, 2FA 복구 등에 활용됩니다.
            </v-alert>

            <template v-if="!emailCodeSent">
              <v-text-field v-model="verifyEmail" label="이메일 주소" prepend-inner-icon="mdi-email"
                type="email" @keyup.enter="sendEmailCode" class="mb-2" />
              <v-btn block color="primary" size="large" :loading="loading" @click="sendEmailCode">
                인증 코드 발송
              </v-btn>
            </template>
            <template v-else>
              <v-alert type="success" variant="tonal" class="mb-4">
                <strong>{{ verifyEmail }}</strong>으로 6자리 코드를 보냈습니다.
              </v-alert>
              <v-otp-input v-model="emailCode" length="6" @finish="confirmEmailCode" />
              <v-btn block color="primary" size="large" :loading="loading" @click="confirmEmailCode" class="mt-4">인증 확인</v-btn>
              <v-btn block variant="text" color="primary" @click="emailCodeSent=false" class="mt-2">다시 보내기</v-btn>
            </template>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
        </v-card>

        <!-- ═══ 비밀번호 찾기 ═══ -->
        <v-card v-else-if="step === 'forgot-pw'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">🔑 비밀번호 찾기</v-card-title>
          <v-card-text>
            <p class="text-center mb-4" style="color:#8B949E;">가입 시 등록한 이메일로 재설정 링크를 보내드립니다</p>
            <v-text-field v-model="resetEmail" label="이메일 주소" prepend-inner-icon="mdi-email"
              type="email" @keyup.enter="forgotPassword" class="mb-2" />
            <v-btn block color="primary" size="large" :loading="loading" @click="forgotPassword">재설정 링크 발송</v-btn>
            <v-btn block variant="text" color="primary" @click="step = 'login'" class="mt-2">돌아가기</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
          <v-alert v-if="successMsg" type="success" variant="tonal" class="mx-4 mb-4">{{ successMsg }}</v-alert>
        </v-card>

        <!-- ═══ 비밀번호 재설정 ═══ -->
        <v-card v-else-if="step === 'reset-pw'" class="pa-6" style="border: 1px solid rgba(88,166,255,0.15);">
          <v-card-title class="text-center">🔑 새 비밀번호 설정</v-card-title>
          <v-card-text>
            <v-text-field v-model="newPassword" label="새 비밀번호 (8자 이상)" type="password"
              prepend-inner-icon="mdi-lock" class="mb-1" />
            <v-text-field v-model="newPasswordConfirm" label="비밀번호 확인" type="password"
              prepend-inner-icon="mdi-lock-check" @keyup.enter="resetPassword" class="mb-2" />
            <v-btn block color="primary" size="large" :loading="loading" @click="resetPassword">비밀번호 변경</v-btn>
          </v-card-text>
          <v-alert v-if="error" type="error" variant="tonal" class="mx-4 mb-4">{{ error }}</v-alert>
          <v-alert v-if="successMsg" type="success" variant="tonal" class="mx-4 mb-4">{{ successMsg }}</v-alert>
        </v-card>

      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '../store/auth'
import api from '../api'

const router = useRouter()
const route = useRoute()
const auth = useAuthStore()

const step = ref('login')
const username = ref('')
const password = ref('')
const displayName = ref('')
const totpCode = ref('')
const recoveryCode = ref('')
const inviteCode = ref('')
const inviteVerified = ref(false)
const tempToken = ref('')
const totpSecret = ref('')
const qrBase64 = ref('')
const recoveryCodes = ref([])
const recoveryConfirmed = ref(false)
const loading = ref(false)
const error = ref('')
const successMsg = ref('')
const pendingAccess = ref('')
const pendingRefresh = ref('')

// 이메일 인증
const verifyEmail = ref('')
const emailCode = ref('')
const emailCodeSent = ref(false)

// 비밀번호 찾기/재설정
const resetEmail = ref('')
const resetToken = ref('')
const newPassword = ref('')
const newPasswordConfirm = ref('')

// 2FA 이메일 복구
const emailRecoveryCode = ref('')
const maskedEmail = ref('')

// Discord 콜백 + 비밀번호 재설정 링크 처리
onMounted(() => {
  const q = route.query
  if (q.discord_error) { error.value = decodeURIComponent(q.discord_error); return }
  if (q.reset_token) { resetToken.value = q.reset_token; step.value = 'reset-pw'; return }
  if (q.discord === '1') {
    tempToken.value = q.token || ''
    if (q.status === '2fa_setup_required') { setupQR(); step.value = 'setup-qr' }
    else if (q.status === '2fa_required') { step.value = '2fa' }
    else if (q.status === 'authenticated') {
      auth.setTokens(q.access, q.refresh); auth.fetchUser(); router.push('/')
    }
  }
})

function discordLogin() { window.location.href = '/api/auth/discord/login' }

async function login() {
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/login', { username: username.value, password: password.value })
    tempToken.value = r.data.temp_token || ''
    if (r.data.status === '2fa_setup_required') { await setupQR(); step.value = 'setup-qr' }
    else if (r.data.status === '2fa_required') { step.value = '2fa' }
    else { auth.setTokens(r.data.access_token, r.data.refresh_token); await auth.fetchUser(); router.push('/') }
  } catch(e) { error.value = e.response?.data?.detail || '로그인 실패' }
  finally { loading.value = false }
}

async function setupQR() {
  const r = await api.post('/api/auth/totp/setup', null, { params: { temp_token: tempToken.value } })
  totpSecret.value = r.data.secret; qrBase64.value = r.data.qr_code_base64
}

async function activateTotp() {
  if (totpCode.value.length !== 6) return
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/totp/activate', { temp_token: tempToken.value, totp_code: totpCode.value })
    recoveryCodes.value = r.data.recovery_codes
    pendingAccess.value = r.data.access_token
    pendingRefresh.value = r.data.refresh_token
    // email_verify_required 플래그 저장
    if (r.data.email_verify_required) { pendingEmailVerify.value = true }
    step.value = 'show-recovery'
  } catch(e) { error.value = e.response?.data?.detail || '실패'; totpCode.value = '' }
  finally { loading.value = false }
}

const pendingEmailVerify = ref(false)

async function verify2fa() {
  if (totpCode.value.length !== 6) return
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/verify-2fa', { temp_token: tempToken.value, totp_code: totpCode.value })
    if (r.data.email_verify_required) {
      tempToken.value = r.data.access_token // email_verify용 temp_token
      step.value = 'email-verify'
    } else {
      auth.setTokens(r.data.access_token, r.data.refresh_token); await auth.fetchUser(); router.push('/')
    }
  } catch(e) { error.value = e.response?.data?.detail || '실패'; totpCode.value = '' }
  finally { loading.value = false }
}

async function verifyRecovery() {
  if (recoveryCode.value.length !== 8) return
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/verify-recovery', { temp_token: tempToken.value, recovery_code: recoveryCode.value })
    if (r.data.email_verify_required) {
      tempToken.value = r.data.access_token
      step.value = 'email-verify'
    } else {
      auth.setTokens(r.data.access_token, r.data.refresh_token); await auth.fetchUser(); router.push('/')
    }
  } catch(e) { error.value = e.response?.data?.detail || '실패'; recoveryCode.value = '' }
  finally { loading.value = false }
}

function finishSetup() {
  if (pendingEmailVerify.value) {
    tempToken.value = pendingAccess.value
    step.value = 'email-verify'
  } else {
    auth.setTokens(pendingAccess.value, pendingRefresh.value); auth.fetchUser(); router.push('/')
  }
}

// ─── 이메일 인증 ───
async function sendEmailCode() {
  if (!verifyEmail.value) return
  loading.value = true; error.value = ''
  try {
    await api.post('/api/auth/verify-email/send', { temp_token: tempToken.value, email: verifyEmail.value })
    emailCodeSent.value = true
  } catch(e) { error.value = e.response?.data?.detail || '발송 실패' }
  finally { loading.value = false }
}

async function confirmEmailCode() {
  if (emailCode.value.length !== 6) return
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/verify-email/confirm', { temp_token: tempToken.value, code: emailCode.value })
    auth.setTokens(r.data.access_token, r.data.refresh_token); await auth.fetchUser(); router.push('/')
  } catch(e) { error.value = e.response?.data?.detail || '인증 실패'; emailCode.value = '' }
  finally { loading.value = false }
}

// ─── 비밀번호 찾기/재설정 ───
async function forgotPassword() {
  if (!resetEmail.value) return
  loading.value = true; error.value = ''; successMsg.value = ''
  try {
    const r = await api.post('/api/auth/forgot-password', { email: resetEmail.value })
    successMsg.value = r.data.message
  } catch(e) { error.value = e.response?.data?.detail || '실패' }
  finally { loading.value = false }
}

async function resetPassword() {
  if (newPassword.value.length < 8) { error.value = '비밀번호는 8자 이상이어야 합니다'; return }
  if (newPassword.value !== newPasswordConfirm.value) { error.value = '비밀번호가 일치하지 않습니다'; return }
  loading.value = true; error.value = ''; successMsg.value = ''
  try {
    const r = await api.post('/api/auth/reset-password', { token: resetToken.value, new_password: newPassword.value })
    successMsg.value = r.data.message
    setTimeout(() => { step.value = 'login' }, 2000)
  } catch(e) { error.value = e.response?.data?.detail || '재설정 실패' }
  finally { loading.value = false }
}

// ─── 2FA 이메일 복구 ───
async function send2faRecovery() {
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/recover-2fa/send', { temp_token: tempToken.value })
    maskedEmail.value = r.data.message
    step.value = '2fa-email-recovery'
  } catch(e) { error.value = e.response?.data?.detail || '실패' }
  finally { loading.value = false }
}

async function confirm2faRecovery() {
  if (emailRecoveryCode.value.length !== 6) return
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/auth/recover-2fa/confirm', { temp_token: tempToken.value, code: emailRecoveryCode.value })
    tempToken.value = r.data.temp_token
    await setupQR()
    step.value = 'setup-qr'
  } catch(e) { error.value = e.response?.data?.detail || '복구 실패'; emailRecoveryCode.value = '' }
  finally { loading.value = false }
}

// ─── 유틸 ───
async function verifyInvite() {
  loading.value = true; error.value = ''
  try {
    const r = await api.get(`/api/invite/verify/${inviteCode.value}`)
    if (r.data.valid) { inviteVerified.value = true } else { error.value = r.data.reason }
  } catch(e) { error.value = '코드 확인 실패' }
  finally { loading.value = false }
}

async function registerInvite() {
  loading.value = true; error.value = ''
  try {
    const r = await api.post('/api/invite/register', {
      invite_code: inviteCode.value, username: username.value,
      password: password.value, display_name: displayName.value || null,
    })
    tempToken.value = r.data.temp_token; await setupQR(); step.value = 'setup-qr'
  } catch(e) { error.value = e.response?.data?.detail || '가입 실패' }
  finally { loading.value = false }
}

function dlRecovery() {
  const t = `Game Panel 복구 코드\n${new Date().toLocaleString('ko-KR')}\n\n${recoveryCodes.value.map((c,i)=>`${i+1}. ${c}`).join('\n')}\n\n⚠️ 1회용입니다. 안전하게 보관하세요.`
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t])); a.download = 'game-panel-recovery.txt'; a.click()
}
</script>

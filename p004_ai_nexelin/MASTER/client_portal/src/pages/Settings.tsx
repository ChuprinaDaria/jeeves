import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import { useTranslation } from 'react-i18next'
import { useAuthStore } from '../stores/auth'

type ClientMe = {
  id: number
  company_name: string
  custom_system_prompt?: string
  features?: Record<string, any>
  logo?: string
}

type EmailReportConfig = {
  email_report_enabled: boolean
  email_report_recipients: string[]
}

export default function Settings(){
  const [me, setMe] = useState<ClientMe|null>(null)
  const [prompt, setPrompt] = useState('')
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [logoFile, setLogoFile] = useState<File|null>(null)
  const [logoPreview, setLogoPreview] = useState<string|null>(null)
  const [uploadingLogo, setUploadingLogo] = useState(false)
  const [reportEnabled, setReportEnabled] = useState(false)
  const [reportRecipients, setReportRecipients] = useState<string[]>([])
  const [newRecipient, setNewRecipient] = useState('')
  const [savingReport, setSavingReport] = useState(false)
  const [sendingDigest, setSendingDigest] = useState(false)
  const [reportMsg, setReportMsg] = useState('')
  const { t } = useTranslation()
  const auth = useAuthStore(s=>({ access: s.access, loading: s.loading }))

  async function load(){
    const { data } = await api.get('/api/clients/me/')
    setMe(data)
    setPrompt(data.custom_system_prompt || '')
    if (data.logo) {
      setLogoPreview(data.logo)
    }
    // Load report settings
    try{
      const res = await api.get<EmailReportConfig>('/api/clients/email-smtp/config/')
      setReportEnabled(!!res.data.email_report_enabled)
      setReportRecipients(Array.isArray(res.data.email_report_recipients) ? res.data.email_report_recipients : [])
    }catch{
      // ignore
    }
  }
  useEffect(()=>{ if(auth.access && !auth.loading){ load().catch(()=>{}) } },[auth.access, auth.loading])

  async function save(){
    setSaving(true); setMessage('')
    try{
      const { data } = await api.patch('/api/clients/me/', { custom_system_prompt: prompt })
      setMe(data)
      setMessage(t('saved'))
      // Після збереження перезавантажимо дані для впевненості
      try{ await load() }catch{}
    }catch(e:any){
      setMessage(e?.response?.data?.error || e.message || 'Save error')
    }finally{
      setSaving(false)
    }
  }

  function handleLogoChange(e: React.ChangeEvent<HTMLInputElement>){
    const file = e.target.files?.[0]
    if (file) {
      // Валідація файлу
      if (!file.type.startsWith('image/')) {
        setMessage(t('logo_upload_error') + ': ' + 'File must be an image')
        return
      }
      if (file.size > 5 * 1024 * 1024) {
        setMessage(t('logo_upload_error') + ': ' + 'File size must be less than 5MB')
        return
      }
      
      setLogoFile(file)
      // Створюємо preview
      const reader = new FileReader()
      reader.onload = (e) => {
        setLogoPreview(e.target?.result as string)
      }
      reader.readAsDataURL(file)
    }
  }

  async function uploadLogo(){
    if (!logoFile) return
    
    setUploadingLogo(true)
    setMessage('')
    try{
      const formData = new FormData()
      formData.append('logo', logoFile)
      
      const { data } = await api.post('/api/clients/logo/', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      })
      
      setMe(prev => prev ? { ...prev, logo: data.logo_url } : null)
      setMessage(t('logo_uploaded'))
      setLogoFile(null)
    }catch(e:any){
      setMessage(t('logo_upload_error') + ': ' + (e?.response?.data?.error || e.message || 'Upload error'))
    }finally{
      setUploadingLogo(false)
    }
  }

  async function removeLogo(){
    setUploadingLogo(true)
    setMessage('')
    try{
      await api.delete('/api/clients/logo/')
      
      setMe(prev => prev ? { ...prev, logo: undefined } : null)
      setLogoPreview(null)
      setMessage(t('logo_deleted'))
    }catch(e:any){
      setMessage(t('logo_upload_error') + ': ' + (e?.response?.data?.error || e.message || 'Delete error'))
    }finally{
      setUploadingLogo(false)
    }
  }

  function isValidEmail(email: string){
    const v = email.trim()
    if(!v) return false
    // basic check (backend will also validate/sanitize)
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)
  }

  function addRecipient(){
    setReportMsg('')
    const email = newRecipient.trim()
    if(!isValidEmail(email)){
      setReportMsg(t('report_invalid_email'))
      return
    }
    const exists = reportRecipients.some(r => r.toLowerCase() === email.toLowerCase())
    if(exists){
      setNewRecipient('')
      return
    }
    if(reportRecipients.length >= 5){
      setReportMsg(t('report_max_recipients'))
      return
    }
    setReportRecipients(prev => [...prev, email])
    setNewRecipient('')
  }

  function removeRecipient(email: string){
    setReportRecipients(prev => prev.filter(r => r !== email))
  }

  async function saveReportSettings(){
    setSavingReport(true)
    setReportMsg('')
    try{
      const payload = {
        email_report_enabled: reportEnabled,
        email_report_recipients: reportRecipients,
      }
      await api.patch('/api/clients/email-smtp/config/', payload)
      setReportMsg(t('saved'))
    }catch(e:any){
      setReportMsg(e?.response?.data?.error || e.message || 'Save error')
    }finally{
      setSavingReport(false)
    }
  }

  async function sendDailyReportNow(){
    setSendingDigest(true)
    setReportMsg('')
    try{
      const { data } = await api.post('/api/clients/reports/daily-digest/send/', {})
      if(data?.success){
        setReportMsg(t('report_scheduled'))
      }else{
        setReportMsg(data?.error || 'Error')
      }
    }catch(e:any){
      setReportMsg(e?.response?.data?.error || e.message || 'Error')
    }finally{
      setSendingDigest(false)
    }
  }

  return (
    <div className="grid" style={{gap:20}}>
      <div className="card">
        <h2 style={{marginTop:0}}>{t('settings')}</h2>

        <div className="label">{t('system_prompt')}</div>
        <textarea
          className="input"
          style={{minHeight:180}}
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
        />

        <div className="form-actions">
          <button
            className="btn btn--primary"
            onClick={save}
            disabled={saving}
          >
            {saving ? t('loading') : t('save')}
          </button>
        </div>


        {message && <div className="form-message">{message}</div>}
      </div>

      <div className="card">
        <h2 style={{marginTop:0}}>{t('report_settings')}</h2>

        <label style={{display:'flex', alignItems:'center', gap:10, marginBottom:12}}>
          <input
            type="checkbox"
            checked={reportEnabled}
            onChange={(e)=>setReportEnabled(e.target.checked)}
          />
          <span>{t('report_enabled')}</span>
        </label>

        <div className="label">{t('report_recipients')}</div>
        <div style={{display:'flex', gap:8, marginBottom:10}}>
          <input
            className="input"
            value={newRecipient}
            placeholder={t('report_email_placeholder')}
            onChange={(e)=>setNewRecipient(e.target.value)}
            onKeyDown={(e)=>{
              if(e.key === 'Enter'){
                e.preventDefault()
                addRecipient()
              }
            }}
          />
          <button className="btn btn--secondary" onClick={addRecipient}>
            {t('add')}
          </button>
        </div>

        {reportRecipients.length > 0 ? (
          <div style={{display:'flex', flexDirection:'column', gap:6, marginBottom:14}}>
            {reportRecipients.map((email)=>(
              <div key={email} style={{display:'flex', justifyContent:'space-between', alignItems:'center', gap:10}}>
                <div style={{fontFamily:'monospace'}}>{email}</div>
                <button className="btn btn--danger" onClick={()=>removeRecipient(email)}>
                  {t('remove')}
                </button>
              </div>
            ))}
          </div>
        ) : (
          <div style={{fontSize:'0.9em', color:'#666', marginBottom:14}}>
            {t('report_no_recipients')}
          </div>
        )}

        <div className="form-actions" style={{display:'flex', gap:10, flexWrap:'wrap'}}>
          <button
            className="btn btn--primary"
            onClick={saveReportSettings}
            disabled={savingReport}
          >
            {savingReport ? t('loading') : t('save')}
          </button>
          <button
            className="btn btn--success"
            onClick={sendDailyReportNow}
            disabled={sendingDigest}
          >
            {sendingDigest ? t('loading') : t('send_daily_report')}
          </button>
        </div>

        {reportMsg && <div className="form-message">{reportMsg}</div>}
      </div>


      <div className="card">
        <h2>{t('logo')}</h2>
        <div className="label">{t('logo_help')}</div>
        <div style={{fontSize: '0.9em', color: '#666', marginBottom: 16}}>
          {t('logo_requirements')}
        </div>
        
        {logoPreview && (
          <div style={{marginBottom: 16}}>
            <div className="label">{t('logo_preview')}</div>
            <img 
              src={logoPreview} 
              alt="Logo preview" 
              style={{
                maxWidth: 200, 
                maxHeight: 200, 
                border: '1px solid #ddd', 
                borderRadius: 8,
                padding: 8
              }} 
            />
          </div>
        )}
        
        <div className="logo-actions">
          <input
            type="file"
            accept="image/*"
            onChange={handleLogoChange}
            style={{ display: 'none' }}
            id="logo-upload"
          />
          
          <label htmlFor="logo-upload" className="btn btn--secondary" style={{ cursor: 'pointer' }}>
            {t('logo_upload')}
          </label>
              
          {logoFile && (
            <button
              className="btn btn--success"
              onClick={uploadLogo}
              disabled={uploadingLogo}
            >
              {uploadingLogo ? t('loading') : t('upload')}
            </button>
          )}
        
          {me?.logo && (
            <button
              className="btn btn--danger"
              onClick={removeLogo}
              disabled={uploadingLogo}
            >
              {uploadingLogo ? t('loading') : t('logo_remove')}
            </button>
          )}
        </div>


        
        {logoFile && (
          <div style={{marginTop: 8, fontSize: '0.9em', color: '#666'}}>
            {t('file')}: {logoFile.name} ({(logoFile.size / 1024 / 1024).toFixed(2)} MB)
          </div>
        )}
      </div>
    </div>
  )
}

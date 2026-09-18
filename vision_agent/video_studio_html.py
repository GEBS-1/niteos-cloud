# -*- coding: utf-8 -*-
"""Separate Video Studio window — photo → short video concept (MVP shell)."""

VIDEO_STUDIO_HTML = r"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>NITEOS · Video Studio</title>
<style>
  :root{
    --bg:#0b1016; --card:#121a22; --line:#243040; --text:#e8eef5; --muted:#93a0ae;
    --accent:#3dd6c6; --accent2:#5b8cff;
  }
  *{box-sizing:border-box}
  body{margin:0;font-family:"Segoe UI",system-ui,sans-serif;background:radial-gradient(1200px 600px at 10% -10%,#163047,transparent),var(--bg);color:var(--text)}
  header{display:flex;justify-content:space-between;align-items:center;padding:18px 24px;border-bottom:1px solid var(--line)}
  header a{color:var(--muted);text-decoration:none;margin-left:14px}
  header a:hover{color:var(--accent)}
  .brand{font-weight:700;letter-spacing:.04em}
  main{max-width:1100px;margin:0 auto;padding:28px 20px 60px;display:grid;gap:18px;grid-template-columns:1.2fr .8fr}
  @media (max-width:900px){main{grid-template-columns:1fr}}
  .card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:18px}
  h1{font-size:1.45rem;margin:0 0 8px}
  p{color:var(--muted);line-height:1.45}
  .drop{border:1.5px dashed #355066;border-radius:14px;min-height:220px;display:grid;place-items:center;background:#0a1219;overflow:hidden;cursor:pointer}
  .drop img,.drop video{max-width:100%;max-height:360px;object-fit:contain}
  label{display:block;margin:12px 0 6px;font-size:.85rem;color:var(--muted)}
  textarea,select,input[type=text]{width:100%;background:#0a1219;border:1px solid var(--line);border-radius:10px;color:var(--text);padding:10px 12px}
  textarea{min-height:110px;resize:vertical}
  .row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
  button{appearance:none;border:0;border-radius:10px;padding:11px 16px;font-weight:600;cursor:pointer;background:linear-gradient(135deg,var(--accent),var(--accent2));color:#041018}
  button.secondary{background:#1a2531;color:var(--text);border:1px solid var(--line)}
  button:disabled{opacity:.55;cursor:wait}
  .status{margin-top:12px;font-size:.9rem;color:var(--muted);min-height:1.2em}
  .status.err{color:#ff8f8f}
  .status.ok{color:#7dffc3}
  .hint{font-size:.82rem;color:#7f8d9c;margin-top:10px}
  ul{margin:8px 0 0 18px;color:var(--muted)}
</style>
</head>
<body>
<header>
  <div class="brand">NITEOS Video Studio</div>
  <nav>
    <a href="/studio">AI Studio</a>
    <a href="/dealer">Дилер</a>
    <a href="/">Сайт</a>
  </nav>
</header>
<main>
  <section class="card">
    <h1>Видео по объекту</h1>
    <p>Загрузите фото фасада или готовый ночной рендер — получите короткий ролик для КП и согласования с заказчиком.</p>
    <div class="drop" id="drop" tabindex="0">Перетащите фото сюда или кликните для выбора</div>
    <input type="file" id="file" accept="image/*" hidden/>
    <label for="prompt">Что показать в ролике</label>
    <textarea id="prompt" placeholder="Например: плавный облёт ночного фасада, акцент на карнизной подсветке MAGISTRAL, 4–6 секунд"></textarea>
    <div class="row">
      <div style="flex:1;min-width:160px">
        <label for="mode">Режим</label>
        <select id="mode">
          <option value="from_photo">Из дневного фото</option>
          <option value="from_render">Из готового рендера Studio</option>
          <option value="before_after">До / после</option>
        </select>
      </div>
      <div style="flex:1;min-width:160px">
        <label for="duration">Длительность</label>
        <select id="duration">
          <option value="4">~4 сек</option>
          <option value="6" selected>~6 сек</option>
          <option value="8">~8 сек</option>
        </select>
      </div>
    </div>
    <div class="row">
      <button id="btnGen" type="button">Создать видео</button>
      <button class="secondary" id="btnStudio" type="button">Открыть AI Studio</button>
    </div>
    <div class="status" id="status"></div>
    <p class="hint">MVP: окно и API готовы. Генерация подключается к video-модели RouterAI / внешнему провайдеру через ключ <code>VIDEO_API_KEY</code>.</p>
  </section>
  <aside class="card">
    <h1>Как пользоваться</h1>
    <ul>
      <li>Сначала сделайте статичный рендер в AI Studio.</li>
      <li>Перенесите результат сюда или загрузите исходное фото.</li>
      <li>Текстом опишите движение камеры и акценты света.</li>
      <li>Ролик — для презентации и согласования до тяжёлого 3D.</li>
    </ul>
    <div id="previewWrap" style="margin-top:16px"></div>
  </aside>
</main>
<script>
let projectId = new URLSearchParams(location.search).get('project') || '';
let uploadFile = null;
const drop = document.getElementById('drop');
const fileInput = document.getElementById('file');
const statusEl = document.getElementById('status');
function setStatus(text, kind){
  statusEl.textContent = text || '';
  statusEl.className = 'status' + (kind ? ' ' + kind : '');
}
function showPreview(file){
  const url = URL.createObjectURL(file);
  drop.innerHTML = '<img alt="preview" src="'+url+'"/>';
}
drop.addEventListener('click', ()=> fileInput.click());
drop.addEventListener('dragover', (e)=>{ e.preventDefault(); drop.style.borderColor = '#3dd6c6'; });
drop.addEventListener('dragleave', ()=>{ drop.style.borderColor = '#355066'; });
drop.addEventListener('drop', (e)=>{
  e.preventDefault(); drop.style.borderColor = '#355066';
  const f = e.dataTransfer.files && e.dataTransfer.files[0];
  if(f){ uploadFile = f; showPreview(f); }
});
fileInput.addEventListener('change', ()=>{
  const f = fileInput.files && fileInput.files[0];
  if(f){ uploadFile = f; showPreview(f); }
});
document.getElementById('btnStudio').onclick = ()=>{
  location.href = projectId ? ('/studio?project='+encodeURIComponent(projectId)) : '/studio';
};
document.getElementById('btnGen').onclick = async ()=>{
  const prompt = (document.getElementById('prompt').value || '').trim();
  const mode = document.getElementById('mode').value;
  const duration = document.getElementById('duration').value;
  if(!uploadFile && !projectId){
    setStatus('Загрузите фото или откройте страницу с ?project=…', 'err');
    return;
  }
  const btn = document.getElementById('btnGen');
  btn.disabled = true;
  setStatus('Готовлю задачу на видео…');
  try{
    const fd = new FormData();
    fd.append('prompt', prompt);
    fd.append('mode', mode);
    fd.append('duration_sec', duration);
    if(uploadFile) fd.append('image', uploadFile, uploadFile.name || 'facade.png');
    if(projectId) fd.append('project_id', projectId);
    const res = await fetch('/api/video/generate', { method:'POST', body: fd });
    const data = await res.json().catch(()=>({}));
    if(!res.ok){
      throw new Error(data.detail || data.message || ('HTTP '+res.status));
    }
    setStatus(data.message || 'Задача принята', data.ok ? 'ok' : 'err');
    if(data.preview_note){
      document.getElementById('previewWrap').innerHTML = '<p class="hint">'+data.preview_note+'</p>';
    }
    if(data.project_id) projectId = data.project_id;
  }catch(err){
    setStatus(String(err.message || err), 'err');
  }finally{
    btn.disabled = false;
  }
};
</script>
</body>
</html>
"""

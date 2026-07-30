# -*- coding: utf-8 -*-
"""Vision Agent Studio HTML page."""

AGENT_STUDIO_HTML = r"""
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="icon" href="/favicon.ico" sizes="any">
  <title>NITEOS AI-студия</title>
  <style>
    :root{--bg:#070b10;--card:#0f151c;--line:#2b333d;--text:#eef2f6;--muted:#9aa6b2;--accent:#f5b942;--accent2:#5a8fd4}
    *{box-sizing:border-box}
    body{margin:0;background:var(--bg);color:var(--text);font:14px/1.45 Segoe UI,Arial,sans-serif;padding-bottom:78px}
    a{color:#9ec5ff;text-decoration:none}
    header{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:14px 18px;border-bottom:1px solid var(--line);background:#0a1016;position:relative;z-index:5;flex-wrap:wrap}
    h1{margin:0;font-size:20px}
    .muted{color:var(--muted)}
    .btn{border:0;border-radius:10px;padding:10px 14px;font:inherit;font-weight:700;cursor:pointer;background:#d8e0ea;color:#0a1016;text-decoration:none;display:inline-flex;align-items:center;justify-content:center}
    .btn.secondary{background:#1a222c;color:var(--text);border:1px solid var(--line)}
    .btn.accent{background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000}
    .btn:disabled{opacity:.45;cursor:not-allowed}
    .header-actions{display:flex;gap:8px;flex-wrap:wrap;align-items:center;position:relative;z-index:6}
    .layout{display:grid;grid-template-columns:minmax(240px,1fr) minmax(320px,1.4fr) minmax(280px,1fr);gap:14px;padding:14px;min-height:calc(100vh - 64px)}
    @media(max-width:1100px){.layout{grid-template-columns:1fr}}
    .card{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:12px;display:flex;flex-direction:column;gap:10px;min-height:0}
    .card h2{margin:0;font-size:15px}
    .preview{width:100%;border-radius:10px;background:#05070a;border:1px solid var(--line);object-fit:contain;max-height:280px}
    .preview.lg{max-height:520px;min-height:280px}
    .tags{display:flex;flex-wrap:wrap;gap:6px}
    .tag{padding:4px 8px;border-radius:999px;background:#17202a;border:1px solid #2f3a46;font-size:12px;color:#c9d5e0}
    .meta{font-size:12px;color:var(--muted);line-height:1.4}
    .chat{flex:1;overflow:auto;display:flex;flex-direction:column;gap:8px;padding:4px;min-height:280px;max-height:55vh}
    .bubble{padding:8px 10px;border-radius:10px;max-width:95%;white-space:pre-wrap}
    .bubble.user{align-self:flex-end;background:#1c334d}
    .bubble.assistant{align-self:flex-start;background:#17202a;border:1px solid #2f3a46}
    .chat-input{display:flex;flex-direction:column;gap:8px}
    textarea{width:100%;min-height:72px;resize:vertical;border-radius:10px;border:1px solid var(--line);background:#090d12;color:var(--text);padding:10px;font:inherit}
    .quick{display:flex;flex-wrap:wrap;gap:6px}
    .quick button{font-size:12px;padding:7px 10px;transition:outline .15s,background .15s,border-color .15s,opacity .15s,transform .15s}
    .quick-group{display:none;flex-wrap:wrap;gap:6px;width:100%;padding:8px;border-radius:12px;border:1px dashed transparent;background:transparent}
    .quick-group.open{display:flex}
    .quick-group.for-brush{border-color:rgba(255,107,107,.45);background:rgba(255,70,70,.08)}
    .quick-group.for-eraser{border-color:rgba(79,209,197,.45);background:rgba(79,209,197,.08)}
    .quick-group .group-label{width:100%;font-size:11px;color:var(--muted);margin:0 0 2px}
    .quick button.lit-brush{background:rgba(255,70,70,.22);border-color:#ff6b6b;color:#ffd0d0;outline:2px solid rgba(255,107,107,.55);outline-offset:1px;transform:translateY(-1px)}
    .quick button.lit-eraser{background:rgba(79,209,197,.2);border-color:#4fd1c5;color:#c8fff8;outline:2px solid rgba(79,209,197,.55);outline-offset:1px;transform:translateY(-1px)}
    .quick button.dim{opacity:.38}
    .row{display:flex;gap:8px;flex-wrap:wrap;align-items:center}
    .status{padding:8px 10px;border-radius:10px;background:#121820;border:1px solid #2a3340;font-size:12px}
    .status.busy{border-color:#f5b942;color:#f5d28a}
    .status.err{border-color:#c45;color:#f0a0a0}
    .hist{display:flex;gap:8px;overflow:auto;padding-bottom:4px}
    .hist img{width:72px;height:54px;object-fit:cover;border-radius:8px;border:1px solid var(--line);cursor:pointer}
    .hist-item{flex:0 0 auto;width:86px;border:1px solid var(--line);border-radius:10px;background:#0a1016;padding:5px;cursor:pointer;color:var(--muted);font-size:10px;text-align:left}
    .hist-item.active{border-color:var(--accent);box-shadow:0 0 0 1px rgba(245,185,66,.35)}
    .hist-item img{width:100%;height:54px;object-fit:cover;border-radius:6px;display:block;margin-bottom:4px;border:0}
    .hist-item span{display:block;line-height:1.25;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
    .hist-hint{font-size:12px;color:var(--muted);margin:0}
    input[type=file]{width:100%;font:inherit;color:var(--muted)}
    .hidden{display:none!important}
    .dropzone{border:1.5px dashed #3a4654;border-radius:12px;padding:14px;background:#0a1016;cursor:pointer;transition:border-color .15s,background .15s;text-align:center}
    .dropzone:hover,.dropzone:focus{border-color:var(--accent);outline:none}
    .dropzone.dragover{border-color:var(--accent);background:#151c10}
    .dropzone.has-image{padding:8px;text-align:left}
    .dropzone .hint{font-size:13px;color:var(--muted);line-height:1.45}
    .dropzone .hint strong{color:var(--text);font-weight:700}
    .dropzone .hint kbd{display:inline-block;padding:1px 6px;border:1px solid #3a4654;border-radius:6px;background:#121820;font:12px Consolas,monospace;color:#d7e0ea}
    .dropzone .preview{max-height:220px;margin-top:8px;display:none}
    .dropzone.has-image .preview{display:block}
    .dropzone.has-image .hint{display:none}
    .drop-actions{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}
    .result-stage{position:relative;border:1px solid var(--line);border-radius:12px;background:#030405;min-height:280px;max-height:520px;display:flex;align-items:center;justify-content:center;overflow:hidden}
    .result-stage img{max-width:100%;max-height:520px;width:auto;height:auto;object-fit:contain;border:0;border-radius:0;pointer-events:none;user-select:none}
    .result-stage canvas{position:absolute;left:0;top:0;touch-action:none;cursor:crosshair;z-index:2;pointer-events:none}
    .result-stage.is-editing canvas.tool-on{pointer-events:auto}
    .result-stage.is-editing{outline:2px solid #5a8fd4;outline-offset:1px}
    .markup-bar{display:flex;flex-wrap:wrap;gap:6px;align-items:center}
    .markup-bar .btn.active{outline:2px solid var(--accent);outline-offset:1px}
    .markup-bar .btn.active.brush{outline-color:#ff6b6b}
    .markup-bar .btn.active.eraser{outline-color:#4fd1c5}
    .markup-bar .brush-size{display:flex;align-items:center;gap:6px;font-size:12px;color:var(--muted)}
    .markup-bar .brush-size input{width:100px}
    .legend{font-size:12px;color:var(--muted);line-height:1.45}
    .legend b.red{color:#ff6b6b}.legend b.cyan{color:#4fd1c5}
    .help-btn-promo{border:0;border-radius:10px;padding:10px 14px;font:inherit;font-weight:800;cursor:pointer;background:linear-gradient(135deg,#f5b942,#e88a12);color:#1a1000;text-decoration:none;display:inline-flex;align-items:center}
    .tour-backdrop{position:fixed;inset:0;background:rgba(0,0,0,.62);z-index:90;display:none;align-items:center;justify-content:center;padding:18px}
    .tour-backdrop.open{display:flex}
    .tour-modal{max-width:480px;width:100%;background:#0f151c;border:1px solid #2b333d;border-radius:16px;padding:18px;box-shadow:0 20px 50px rgba(0,0,0,.45)}
    .tour-modal h3{margin:0 0 8px;font-size:18px}
    .tour-modal p{margin:0 0 10px;color:var(--muted);line-height:1.5}
    .tour-modal ol{margin:0 0 14px;padding-left:18px;color:#dbe4ee;line-height:1.55}
    .tour-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .coach-root{position:fixed;inset:0;z-index:92;display:none;pointer-events:none}
    .coach-root.open{display:block;pointer-events:auto}
    .coach-shade{position:absolute;inset:0;background:rgba(3,6,10,.78);pointer-events:auto}
    .coach-hole{position:absolute;border-radius:14px;box-shadow:0 0 0 9999px rgba(3,6,10,.78),0 0 0 3px rgba(245,185,66,.95),0 0 28px rgba(245,185,66,.35);pointer-events:none;transition:top .2s,left .2s,width .2s,height .2s}
    .coach-card{position:fixed;z-index:93;width:min(360px,calc(100vw - 24px));background:#101820;border:1px solid #3a4654;border-radius:16px;padding:14px 14px 12px;box-shadow:0 18px 40px rgba(0,0,0,.5);color:var(--text)}
    .coach-card .step-n{font-size:11px;color:var(--accent);font-weight:800;letter-spacing:.04em;margin:0 0 4px;text-transform:uppercase}
    .coach-card h3{margin:0 0 6px;font-size:16px}
    .coach-card p{margin:0 0 10px;color:var(--muted);font-size:13px;line-height:1.5}
    .coach-card ol{margin:0 0 12px;padding-left:18px;color:#dbe4ee;font-size:13px;line-height:1.5}
    .coach-actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}
    .tour-pulse{animation:tourPulse 1.2s ease-in-out infinite}
    @keyframes tourPulse{0%,100%{box-shadow:0 0 0 0 rgba(245,185,66,.55)}50%{box-shadow:0 0 0 8px rgba(245,185,66,0)}}
    .tour-target-live{position:relative;z-index:91!important}
    .feedback-zone{border:1px solid var(--line);border-radius:14px;padding:12px;background:#0a1016;display:none;flex-direction:column;gap:8px}
    .feedback-zone.open{display:flex}
    .feedback-votes{display:flex;gap:8px;flex-wrap:wrap}
    .feedback-votes button.active.like{background:#1f3d2a;border-color:#3d8f5a;color:#c8f0d4}
    .feedback-votes button.active.dislike{background:#3d1f24;border-color:#c45;color:#f0c0c0}
    .feedback-zone select,.feedback-zone input{width:100%;border-radius:10px;border:1px solid var(--line);background:#090d12;color:var(--text);padding:10px;font:inherit}
    .feedback-toast{position:fixed;right:16px;bottom:88px;z-index:80;width:min(320px,calc(100vw - 28px));background:rgba(12,16,22,.96);border:1px solid #3a4552;border-radius:14px;padding:14px;box-shadow:0 12px 36px rgba(0,0,0,.45)}
    .feedback-toast.hidden{display:none}
    .feedback-toast-title{margin:0 0 4px;font-size:15px;font-weight:700}
    .feedback-toast-lead{margin:0 0 10px;font-size:12px;color:var(--muted);line-height:1.45}
    .feedback-toast-actions{display:flex;gap:8px;flex-wrap:wrap}
    .feedback-toast-close{position:absolute;top:8px;right:10px;border:0;background:transparent;color:#8d97a3;font-size:18px;cursor:pointer}
    .busy-overlay{position:fixed;inset:0;background:rgba(4,8,12,.72);z-index:95;display:none;align-items:center;justify-content:center;padding:18px}
    .busy-overlay.open{display:flex}
    .busy-modal{max-width:420px;width:100%;background:#0f151c;border:1px solid #3a4654;border-radius:16px;padding:22px 20px;text-align:center;box-shadow:0 20px 50px rgba(0,0,0,.5)}
    .busy-modal h3{margin:0 0 8px;font-size:18px;color:var(--text)}
    .busy-modal p{margin:0;color:var(--muted);line-height:1.5}
    .busy-spinner{width:36px;height:36px;margin:0 auto 14px;border:3px solid #2b333d;border-top-color:var(--accent);border-radius:50%;animation:niteosSpin .8s linear infinite}
    @keyframes niteosSpin{to{transform:rotate(360deg)}}
    .card-head{display:flex;align-items:center;justify-content:space-between;gap:8px}
    .tip{position:relative;display:inline-flex;align-items:center;vertical-align:middle}
    .tip-btn{width:22px;height:22px;border-radius:999px;border:1px solid #3a4654;background:#151c26;color:#c9d5e0;font:700 12px/1 Segoe UI,Arial,sans-serif;cursor:pointer;padding:0}
    .tip-btn:hover,.tip.open .tip-btn{border-color:var(--accent);color:var(--accent)}
    .tip-bubble{display:none;position:absolute;z-index:40;left:0;top:calc(100% + 8px);width:min(280px,70vw);background:#101820;border:1px solid #3a4654;border-radius:12px;padding:10px 12px;color:#dbe4ee;font-size:12px;line-height:1.45;box-shadow:0 12px 28px rgba(0,0,0,.4)}
    .tip.open .tip-bubble{display:block}
    .tip-bubble.right{left:auto;right:0}
    .photo-checklist{margin:0;padding-left:18px;color:#dbe4ee;line-height:1.55;font-size:13px}
    .photo-checklist li{margin:0 0 6px}
    .warn-note{padding:10px 12px;border-radius:10px;background:#1a1510;border:1px solid #5a4630;color:#f0d2a0;font-size:12px;line-height:1.45}
    .guide-strip{display:flex;flex-wrap:wrap;gap:8px;padding:10px 12px;border-radius:12px;background:#0a1016;border:1px dashed #3a4654;font-size:12px;color:var(--muted);line-height:1.4}
    .guide-strip b{color:var(--text)}
    .guide-step{flex:1 1 140px;min-width:120px}
  </style>
</head>
<body>
{{MAX_GROUP_WIDGET}}
<div class="busy-overlay" id="busyOverlay" aria-live="polite">
  <div class="busy-modal">
    <div class="busy-spinner" aria-hidden="true"></div>
    <h3 id="busyTitle">Идёт генерация</h3>
    <p id="busyText">Подождите, агент обрабатывает запрос…</p>
  </div>
</div>
<div class="tour-backdrop" id="photoCheckModal" role="dialog" aria-label="Проверка фото перед генерацией">
  <div class="tour-modal">
    <h3>Проверьте фото перед генерацией</h3>
    <p>Лучше всего подходит <b style="color:#eef2f6">дневной фронтальный снимок фасада</b> без лишнего.</p>
    <ul class="photo-checklist">
      <li>Нет чужих надписей, водяных знаков, стрелок и рамок поверх здания</li>
      <li>Фасад целиком в кадре, без сильного наклона и сильных бликов</li>
      <li>Не ночной уже готовый рендер — исходник лучше дневной</li>
      <li>Без людей/машин на переднем плане, закрывающих стены</li>
    </ul>
    <div class="warn-note" style="margin:12px 0">Если на фото есть надписи или чужой водяной знак — лучше загрузить чистое фото. Иначе агент может сохранить их в результате.</div>
    <div class="tour-actions">
      <button type="button" class="btn secondary" onclick="closePhotoCheck()">Отмена</button>
      <button type="button" class="btn secondary" onclick="closePhotoCheck(); document.getElementById('pickFileBtn').click()">Другое фото</button>
      <button type="button" class="btn accent" onclick="confirmPhotoCheckAndStart()">Всё ок, генерировать</button>
    </div>
  </div>
</div>
<header>
  <div>
    <a class="btn secondary" href="/" id="backHomeBtn" style="margin-bottom:8px">← Назад на главную</a>
    <h1>AI-студия · Vision Agent</h1>
    <div class="muted" id="projectLabel">Новый проект</div>
  </div>
  <div class="header-actions row">
    <!-- К шаблонам временно скрыто
    <a class="btn secondary" href="/dealer" id="dealerLink">К шаблонам</a>
    -->
    <button type="button" class="help-btn-promo" id="helpBtnPromo" onclick="openStudioTour()">Как это работает?</button>
    <button class="btn secondary" id="newProjectTour" onclick="createProject()">Новый проект</button>
  </div>
</header>

<div class="tour-backdrop" id="studioTour" role="dialog" aria-label="Обучение AI-студии" style="display:none">
  <!-- Legacy modal kept unused; interactive coach tour is primary -->
  <div class="tour-modal">
    <h3 id="tourTitle">Как работает AI-агент</h3>
    <div id="tourBody"></div>
    <div class="tour-actions">
      <button type="button" class="btn secondary" id="tourPrevBtn" onclick="prevStudioTour()">← Назад</button>
      <button type="button" class="btn secondary" onclick="closeStudioTour()">Закрыть</button>
      <button type="button" class="btn accent" id="tourNextBtn" onclick="nextStudioTour()">Далее →</button>
    </div>
  </div>
</div>
<div class="coach-root" id="coachRoot" aria-live="polite">
  <div class="coach-shade" id="coachShade" onclick="/* keep open */"></div>
  <div class="coach-hole" id="coachHole"></div>
  <div class="coach-card" id="coachCard">
    <div class="step-n" id="coachStepN">Шаг 1 из 8</div>
    <h3 id="coachTitle">Заголовок</h3>
    <div id="coachBody"></div>
    <div class="coach-actions">
      <button type="button" class="btn secondary" id="coachPrevBtn" onclick="prevStudioTour()">← Назад</button>
      <button type="button" class="btn secondary" onclick="closeStudioTour()">Закрыть</button>
      <button type="button" class="btn accent" id="coachNextBtn" onclick="nextStudioTour()">Далее →</button>
    </div>
  </div>
</div>

<div class="feedback-toast hidden" id="feedbackToast" role="dialog" aria-label="Оценка результата">
  <button type="button" class="feedback-toast-close" onclick="dismissFeedbackToast()" aria-label="Закрыть">×</button>
  <p class="feedback-toast-title">Как вам результат агента?</p>
  <p class="feedback-toast-lead">Краткая оценка поможет обучить AI-студию.</p>
  <div class="feedback-toast-actions">
    <button type="button" class="btn secondary" onclick="quickFeedbackFromToast('like')">Нравится</button>
    <button type="button" class="btn secondary" onclick="quickFeedbackFromToast('dislike')">Не нравится</button>
    <button type="button" class="btn secondary" onclick="dismissFeedbackToast(); openFeedbackZone()">Подробнее</button>
  </div>
</div>
<main class="layout">
  <section class="card">
    <div class="card-head">
      <h2>1. Фото фасада</h2>
      <span class="tip" id="tipSource">
        <button type="button" class="tip-btn" onclick="toggleTip('tipSource')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Сюда загружается исходное фото здания. Дважды нажмите зону, вставьте Ctrl+V или «Выбрать файл». Референс освещения подбирается скрыто — на экране не показывается.</span>
      </span>
    </div>
    <div class="guide-strip" id="guideStrip">
      <div class="guide-step"><b>Шаг 1</b><br>Загрузите дневное фото фасада</div>
      <div class="guide-step"><b>Шаг 2</b><br>«Анализ → генерация»</div>
      <div class="guide-step"><b>Шаг 3</b><br>Правьте результат кистью и чатом</div>
    </div>
    <div class="dropzone" id="dropzone" tabindex="0" role="button" aria-label="Вставить или загрузить фото фасада">
      <div class="hint">
        <strong>Вставьте фото фасада</strong><br>
        Ctrl+V / Cmd+V · перетащите файл · или дважды нажмите сюда<br>
        <span style="opacity:.85">Лучше дневной фронтальный снимок без надписей и водяных знаков</span>
      </div>
      <img class="preview" id="sourceImg" alt="source">
    </div>
    <input type="file" id="sourceFile" class="hidden" accept="image/*">
    <div class="drop-actions">
      <button type="button" class="btn secondary" id="pickFileBtn" title="Открыть выбор файла с диска">Выбрать файл</button>
      <button type="button" class="btn accent" id="startBtn" onclick="startStudio()" disabled title="Сначала загрузите фото">Анализ → генерация</button>
      <span class="tip" id="tipStart">
        <button type="button" class="tip-btn" onclick="toggleTip('tipStart')" aria-label="Подсказка">?</button>
        <span class="tip-bubble">Перед запуском появится проверка фото. Агент сам подберёт стиль света и сделает ночной рендер.</span>
      </span>
    </div>
    <div class="status" id="statusBox">Скопируйте фото и нажмите Ctrl+V — или выберите файл</div>
    <div class="warn-note" id="photoSoftWarn">Перед генерацией: уберите с фото чужие надписи/водяные знаки или загрузите чистое фото фасада — так результат будет чище.</div>
  </section>

  <section class="card">
    <div class="card-head">
      <h2>2. Результат</h2>
      <span class="tip" id="tipResult">
        <button type="button" class="tip-btn" onclick="toggleTip('tipResult')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Здесь появляется ночной рендер. Кисть (красная) — изменить/проставить свет в зоне. Ластик (голубой) — убрать светильник. Затем обязательно напишите задачу в чате и нажмите «Отправить».</span>
      </span>
    </div>
    <div class="result-stage" id="resultStage">
      <img id="finalImg" alt="final">
      <canvas id="editMarkupCanvas" class="hidden" aria-hidden="true"></canvas>
    </div>
    <div class="markup-bar" id="markupBarTour">
      <button type="button" class="btn secondary brush" id="editBrushBtn" onclick="toggleEditTool('brush')" title="Красная кисть: изменить или проставить свет">Кисть · правка</button>
      <button type="button" class="btn secondary eraser" id="editEraserBtn" onclick="toggleEditTool('eraser')" title="Голубой ластик: убрать светильник">Ластик · убрать</button>
      <label class="brush-size">Толщина <input type="range" id="editBrushSize" min="4" max="48" value="16" oninput="updateEditBrushSize(this.value)"></label>
      <button type="button" class="btn secondary" onclick="clearEditMarkup()" title="Стереть разметку и выключить инструменты">Очистить разметку</button>
      <span class="tip" id="tipBrush">
        <button type="button" class="tip-btn" onclick="toggleTip('tipBrush')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Инструменты включаются повторным нажатием. Без текста в чате правка не отправится.</span>
      </span>
    </div>
    <div class="legend">
      1) Включите <b class="red">кисть</b> или <b class="cyan">ластик</b> и отметьте зону.
      2) В чате <b>обязательно</b> напишите задачу: убрать / изменить / <b>проставь прожектор</b> / теплее…
      3) Красная зона + «проставь прожектор» — добавит прибор только там. Голубая — уберёт отмеченное.
      4) «Отправить». Без текста правка по разметке не уйдёт.
    </div>
    <div class="status" id="markupHint" style="display:none;margin-top:4px">Что хотите изменить на отмеченных светильниках? Напишите в чат ниже.</div>
    <div class="row">
      <button class="btn secondary" onclick="downloadFinal()" id="downloadBtn" disabled title="Скачать текущий результат">Скачать</button>
      <button class="btn secondary" onclick="copyFinal()" id="copyFinalBtn" disabled title="Скопировать результат в буфер">Копировать</button>
      <span class="tip" id="tipCopy">
        <button type="button" class="tip-btn" onclick="toggleTip('tipCopy')" aria-label="Подсказка">?</button>
        <span class="tip-bubble">«Копировать» — в буфер. Ctrl+V без результата грузит исходник; с результатом — вставляет копию как рабочее фото.</span>
      </span>
    </div>
    <div class="muted" style="font-size:12px">Ctrl+V: без результата — в источник; с результатом — вставить копию как рабочее фото для правок.</div>
    <div class="card-head" style="margin-top:4px">
      <div class="muted">История версий · клик = сделать активной для правок</div>
      <span class="tip" id="tipHistory">
        <button type="button" class="tip-btn" onclick="toggleTip('tipHistory')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Клик по миниатюре делает эту версию активной. Дальше кисть/чат правят именно её.</span>
      </span>
    </div>
    <p class="hist-hint" id="activeHistoryHint"></p>
    <div class="hist" id="historyStrip"></div>
  </section>

  <section class="card">
    <div class="card-head">
      <h2>3. Чат с агентом</h2>
      <span class="tip" id="tipChat">
        <button type="button" class="tip-btn" onclick="toggleTip('tipChat')" aria-label="Подсказка">?</button>
        <span class="tip-bubble right">Быстрые кнопки только подставляют текст — «Отправить» нажимаете сами. С разметкой текст обязателен.</span>
      </span>
    </div>
    <div class="chat" id="chatBox"></div>
    <div class="quick" id="quickPrompts">
      <div class="quick-group for-eraser" id="quickEraserGroup">
        <div class="group-label">Голубой ластик — варианты:</div>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('убери ТОЛЬКО отмеченные голубым светильники и лучи, все остальные светильники оставь как есть')" title="Убрать отмеченные светильники">Убери отмеченное</button>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('убери отмеченные голубым прожекторы и их лучи, стену оставь как у соседних панелей без затемнения')" title="Убрать прожекторы в зоне">Убери прожекторы</button>
        <button type="button" class="btn secondary lit-eraser" data-tool="eraser" onclick="fillChatPrompt('ослабь или почти погаси только отмеченные голубым лучи, сами соседние светильники не трогай')" title="Ослабить свет в зоне">Ослабь лучи</button>
      </div>
      <div class="quick-group for-brush" id="quickBrushGroup">
        <div class="group-label">Красная кисть — варианты:</div>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('измени ТОЛЬКО отмеченные красным светильники, остальные не трогай')" title="Изменить отмеченное">Измени отмеченное</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('проставь прожектор только в красной отмеченной зоне, остальные светильники не трогай')" title="Проставить прожектор">Проставь прожектор</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('сделай отмеченные красным лучи теплее и мягче, остальные светильники не трогай')" title="Теплее в зоне">Теплее в зоне</button>
        <button type="button" class="btn secondary lit-brush" data-tool="brush" onclick="fillChatPrompt('усилить яркость только отмеченных красным светильников и лучей, остальное не трогай')" title="Ярче в зоне">Ярче в зоне</button>
      </div>
      <button type="button" class="btn secondary" data-tool="any" onclick="fillChatPrompt('теплее')" title="Подставить текст «теплее»">Теплее</button>
      <button type="button" class="btn secondary" data-tool="any" onclick="fillChatPrompt('усиль карниз')" title="Подставить текст про карниз">Усиль карниз</button>
    </div>
    <div class="chat-input" id="chatSendTour">
      <textarea id="chatInput" placeholder="Что хотите изменить? Например: убери левый угловой светильник…"></textarea>
      <button class="btn accent" id="chatBtn" onclick="sendChat()" disabled title="Отправить правку агенту">Отправить</button>
    </div>
    <section class="feedback-zone" id="feedbackZone">
      <h2 style="margin:0;font-size:15px" id="feedbackTitle">Оценка результата</h2>
      <p class="muted" id="feedbackLead" style="margin:0">Нравится работа агента? Оценка пойдёт в обучение.</p>
      <div class="feedback-votes" id="feedbackVotes">
        <button type="button" class="btn secondary like" id="feedbackLikeBtn" onclick="setFeedbackVote('like')">Нравится</button>
        <button type="button" class="btn secondary dislike" id="feedbackDislikeBtn" onclick="setFeedbackVote('dislike')">Не нравится</button>
      </div>
      <select id="feedbackIssue" aria-label="Что улучшить">
        <option value="">Что улучшить (необязательно)</option>
        <option value="placement_incorrect">Расстановка света</option>
        <option value="coverage_incomplete">Не хватает покрытия</option>
        <option value="overlit">Слишком ярко</option>
        <option value="underlit">Мало света</option>
        <option value="style_mismatch">Не тот стиль</option>
        <option value="other">Другое</option>
      </select>
      <textarea id="feedbackComment" placeholder="Комментарий (необязательно)" style="min-height:64px"></textarea>
      <input id="feedbackContact" type="text" placeholder="Email или телефон (необязательно)">
      <button type="button" class="btn accent" onclick="submitFeedback()" id="feedbackSubmitBtn">Отправить отзыв</button>
      <div class="muted" id="feedbackStatus"></div>
    </section>
  </section>
</main>
<script>
let projectId = '';
let busy = false;
let lastState = {};
let editDrawing = false;
let editLastPoint = null;
let editTool = null; // 'brush' | 'eraser' | null (off)
let editBrushSize = 16;
let editMarkupReady = false;
let markupBound = false;
let feedbackVote = '';
let feedbackTimer = null;
let feedbackPromptedHistoryId = '';
let feedbackToastDismissedFor = '';
const FEEDBACK_TOAST_DELAY_MS = 45000;
let tourStep = 0;
let tourActive = false;
let tourResizeBound = false;
const STUDIO_TOUR = [
  {
    title: 'Загрузите фото фасада',
    target: 'dropzone',
    place: 'below',
    html: '<p>Начните здесь.</p><ol><li>Вставьте фото <b>Ctrl+V</b></li><li>или нажмите <b>дважды</b> по этой зоне</li><li>или «Выбрать файл»</li></ol><p>Лучше дневной фронтальный снимок без надписей.</p>'
  },
  {
    title: 'Запуск генерации',
    target: 'startBtn',
    place: 'below',
    html: '<p>Когда фото загружено, нажмите <b>Анализ → генерация</b>.</p><ol><li>Один раз появится проверка качества фото</li><li>Дальше откроется окно «Идёт генерация»</li><li>Результат появится в центре экрана</li></ol>'
  },
  {
    title: 'Готовый результат',
    target: 'resultStage',
    place: 'below',
    html: '<p>Здесь показывается ночной рендер.</p><ol><li>Можно <b>Скачать</b> или <b>Копировать</b></li><li>Дальше правьте кистью / ластиком</li></ol>'
  },
  {
    title: 'Кисть и ластик',
    target: 'markupBarTour',
    place: 'below',
    html: '<p>Инструменты правят только отмеченные зоны.</p><ol><li><b style="color:#ff6b6b">Красная кисть</b> — изменить или проставить свет</li><li><b style="color:#4fd1c5">Голубой ластик</b> — убрать светильник</li><li>Повторное нажатие выключает инструмент</li></ol>'
  },
  {
    title: 'Цветные варианты в чате',
    target: 'quickPrompts',
    place: 'above',
    html: '<p>Когда кисть или ластик включены, здесь загораются цветные кнопки.</p><ol><li>Голубые — для ластика</li><li>Красные — для кисти</li><li>Кнопка только подставляет текст, отправка вручную</li></ol>'
  },
  {
    title: 'Напишите и отправьте',
    target: 'chatSendTour',
    place: 'above',
    html: '<p>С разметкой текст <b>обязателен</b>.</p><ol><li>Выберите цветную кнопку или напишите сами</li><li>Нажмите <b>Отправить</b></li><li>Дождитесь окна правки</li></ol>'
  },
  {
    title: 'История версий',
    target: 'historyStrip',
    place: 'above',
    html: '<p>Каждая генерация/правка сохраняется здесь.</p><ol><li>Клик по миниатюре делает версию <b>активной</b></li><li>Дальнейшие правки идут именно к ней</li></ol>'
  },
  {
    title: 'Новый проект',
    target: 'newProjectTour',
    place: 'below',
    html: '<p>Чтобы начать с чистого листа — <b>Новый проект</b>.</p><ol><li>Экран очистится</li><li>Загрузите новое фото</li><li>Кнопка «Как это работает?» всегда открывает этот тур снова</li></ol>'
  }
];

function qs(){ return new URLSearchParams(location.search); }
function esc(s){ return String(s??'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
async function api(path, opts={}){
  const res = await fetch(path, opts);
  const data = await res.json().catch(()=>({}));
  if(!res.ok) throw new Error(data.detail || res.statusText || 'Ошибка');
  return data;
}
function setBusy(on, msg){
  busy = !!on;
  const box = document.getElementById('statusBox');
  box.classList.toggle('busy', busy);
  box.classList.remove('err');
  if(msg) box.textContent = msg;
  document.getElementById('startBtn').disabled = busy || !projectId;
  const regenBtn = document.getElementById('regenBtn');
  if(regenBtn) regenBtn.disabled = busy || !projectId;
  document.getElementById('chatBtn').disabled = busy || !projectId;
  document.getElementById('downloadBtn').disabled = !lastState.has_final;
  setMarkupEnabled(!!lastState.has_final && !busy);
  const overlay = document.getElementById('busyOverlay');
  const busyText = document.getElementById('busyText');
  const busyTitle = document.getElementById('busyTitle');
  if(overlay){
    overlay.classList.toggle('open', busy);
    overlay.setAttribute('aria-busy', busy ? 'true' : 'false');
  }
  if(busy && busyText && msg) busyText.textContent = msg;
  if(busyTitle){
    busyTitle.textContent = busy
      ? ((msg && /правк|разметк|редактир/i.test(msg)) ? 'Идёт правка' : 'Идёт генерация')
      : 'Идёт генерация';
  }
}
function setError(msg){
  const box = document.getElementById('statusBox');
  box.classList.add('err');
  box.classList.remove('busy');
  box.textContent = msg;
  busy = false;
  const overlay = document.getElementById('busyOverlay');
  if(overlay){
    overlay.classList.remove('open');
    overlay.setAttribute('aria-busy', 'false');
  }
}
function renderChat(chat){
  const box = document.getElementById('chatBox');
  const items = chat || [];
  box.innerHTML = items.map(m => `<div class="bubble ${esc(m.role||'assistant')}">${esc(m.text||'')}</div>`).join('')
    || '<div class="muted">История чата появится после первой генерации</div>';
  box.scrollTop = box.scrollHeight;
}
function applyStudioPayload(data){
  lastState = data || {};
  const st = data.state || {};
  renderChat(data.chat || []);

  const dropzone = document.getElementById('dropzone');
  const sourceImg = document.getElementById('sourceImg');
  if(data.source_url){
    sourceImg.src = data.source_url + '?t=' + Date.now();
    dropzone.classList.add('has-image');
  } else {
    sourceImg.removeAttribute('src');
    sourceImg.src = '';
    dropzone.classList.remove('has-image');
  }

  const finalImg = document.getElementById('finalImg');
  if(data.final_url){
    finalImg.onload = () => { syncEditMarkupCanvas(); setMarkupEnabled(true); };
    finalImg.src = data.final_url + '?t=' + Date.now();
  } else {
    finalImg.onload = null;
    finalImg.removeAttribute('src');
    finalImg.src = '';
    clearEditMarkup();
    setMarkupEnabled(false);
  }

  const hist = document.getElementById('historyStrip');
  const activeId = data.active_history_id;
  hist.innerHTML = (data.history || []).map(h => {
    const label = esc(h.kind || 'render') + (h.id != null ? (' #' + h.id) : '');
    const title = esc((h.note || h.prompt || '').slice(0, 120));
    const active = h.active || String(h.id) === String(activeId);
    return `<button type="button" class="hist-item${active ? ' active' : ''}" title="${title}" onclick="restoreHistoryVersion('${esc(String(h.id))}')">
      <img src="${esc(h.url)}?t=${Date.now()}" alt="">
      <span>${label}${active ? ' · active' : ''}</span>
    </button>`;
  }).join('') || '<div class="muted">История версий появится после генерации</div>';
  const hint = document.getElementById('activeHistoryHint');
  if(hint){
    hint.textContent = activeId != null
      ? ('Активна версия #' + activeId + ' — кисть/ластик и «Отправить» правят её')
      : ((data.history || []).length ? 'Выберите версию в истории, чтобы править именно её' : '');
  }
  document.getElementById('downloadBtn').disabled = !data.has_final;
  const copyBtn = document.getElementById('copyFinalBtn');
  if(copyBtn) copyBtn.disabled = !data.has_final;
  document.getElementById('chatBtn').disabled = !projectId || busy;
  const regenBtnApply = document.getElementById('regenBtn');
  if(regenBtnApply) regenBtnApply.disabled = !projectId || busy;
  setMarkupEnabled(!!data.has_final && !busy);
  updateEditToolUi();
  if(data.has_final) setBusy(false, 'Готово. Включите кисть/ластик, разметьте светильники и отправьте.');
  scheduleFeedbackPrompt(data);
}
function clearTourTarget(){
  document.querySelectorAll('.tour-target-live').forEach(el => el.classList.remove('tour-target-live', 'tour-pulse'));
}
function positionCoachCard(targetRect, place){
  const card = document.getElementById('coachCard');
  if(!card) return;
  const pad = 12;
  const cw = card.offsetWidth || 360;
  const ch = card.offsetHeight || 200;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  let top, left;
  const prefer = place || 'below';
  if(prefer === 'above'){
    top = targetRect.top - ch - 14;
    if(top < pad) top = targetRect.bottom + 14;
  } else {
    top = targetRect.bottom + 14;
    if(top + ch > vh - pad) top = Math.max(pad, targetRect.top - ch - 14);
  }
  left = targetRect.left + (targetRect.width / 2) - (cw / 2);
  left = Math.max(pad, Math.min(left, vw - cw - pad));
  top = Math.max(pad, Math.min(top, vh - ch - pad));
  card.style.top = Math.round(top) + 'px';
  card.style.left = Math.round(left) + 'px';
}
function renderStudioTour(){
  const step = STUDIO_TOUR[tourStep] || STUDIO_TOUR[0];
  const root = document.getElementById('coachRoot');
  const hole = document.getElementById('coachHole');
  const shade = document.getElementById('coachShade');
  clearTourTarget();
  document.getElementById('coachStepN').textContent = 'Шаг ' + (tourStep + 1) + ' из ' + STUDIO_TOUR.length;
  document.getElementById('coachTitle').textContent = step.title;
  document.getElementById('coachBody').innerHTML = step.html;
  document.getElementById('coachPrevBtn').style.visibility = tourStep > 0 ? 'visible' : 'hidden';
  document.getElementById('coachNextBtn').textContent = tourStep >= STUDIO_TOUR.length - 1 ? 'Понятно ✓' : 'Далее →';

  const target = document.getElementById(step.target);
  if(!target){
    // Fallback: center card, full shade
    if(shade) shade.style.display = 'block';
    if(hole) hole.style.display = 'none';
    const card = document.getElementById('coachCard');
    if(card){
      card.style.top = '20%';
      card.style.left = '50%';
      card.style.transform = 'translateX(-50%)';
    }
    return;
  }
  target.classList.add('tour-target-live', 'tour-pulse');
  try{ target.scrollIntoView({behavior:'smooth', block:'center', inline:'nearest'}); }catch(_){}
  // Allow layout settle after scroll
  setTimeout(() => {
    if(!tourActive) return;
    const rect = target.getBoundingClientRect();
    const pad = 8;
    if(shade) shade.style.display = 'none'; // hole shadow paints the dimming
    if(hole){
      hole.style.display = 'block';
      hole.style.top = Math.max(0, rect.top - pad) + 'px';
      hole.style.left = Math.max(0, rect.left - pad) + 'px';
      hole.style.width = Math.max(24, rect.width + pad * 2) + 'px';
      hole.style.height = Math.max(24, rect.height + pad * 2) + 'px';
    }
    const card = document.getElementById('coachCard');
    if(card) card.style.transform = '';
    positionCoachCard({
      top: rect.top - pad,
      left: rect.left - pad,
      width: rect.width + pad * 2,
      height: rect.height + pad * 2,
      bottom: rect.bottom + pad,
      right: rect.right + pad
    }, step.place);
  }, 180);
}
function openStudioTour(){
  tourStep = 0;
  tourActive = true;
  document.getElementById('coachRoot').classList.add('open');
  document.getElementById('studioTour').classList.remove('open');
  renderStudioTour();
  if(!tourResizeBound){
    tourResizeBound = true;
    window.addEventListener('resize', () => { if(tourActive) renderStudioTour(); });
    window.addEventListener('scroll', () => { if(tourActive) renderStudioTour(); }, true);
  }
}
function closeStudioTour(){
  tourActive = false;
  document.getElementById('coachRoot').classList.remove('open');
  document.getElementById('studioTour').classList.remove('open');
  clearTourTarget();
  try{ localStorage.setItem('niteos_studio_tour_seen', '1'); }catch(_){}
}
function prevStudioTour(){
  if(tourStep > 0){ tourStep--; renderStudioTour(); }
}
function nextStudioTour(){
  if(tourStep >= STUDIO_TOUR.length - 1){ closeStudioTour(); return; }
  tourStep++;
  renderStudioTour();
}
function setFeedbackVote(vote){
  feedbackVote = (vote === 'like' || vote === 'dislike') ? vote : '';
  document.getElementById('feedbackLikeBtn').classList.toggle('active', feedbackVote === 'like');
  document.getElementById('feedbackDislikeBtn').classList.toggle('active', feedbackVote === 'dislike');
}
function openFeedbackZone(){
  const zone = document.getElementById('feedbackZone');
  zone.classList.add('open');
  zone.scrollIntoView({behavior:'smooth', block:'nearest'});
}
function hideFeedbackToast(){
  document.getElementById('feedbackToast').classList.add('hidden');
}
function showFeedbackToast(){
  const toast = document.getElementById('feedbackToast');
  if(feedbackToastDismissedFor && feedbackToastDismissedFor === feedbackPromptedHistoryId) return;
  toast.classList.remove('hidden');
}
function dismissFeedbackToast(){
  hideFeedbackToast();
  if(feedbackPromptedHistoryId) feedbackToastDismissedFor = feedbackPromptedHistoryId;
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
}
async function quickFeedbackFromToast(vote){
  setFeedbackVote(vote);
  dismissFeedbackToast();
  await submitFeedback();
}
function scheduleFeedbackPrompt(state){
  const zone = document.getElementById('feedbackZone');
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  if(!state || !state.has_final){
    zone.classList.remove('open');
    hideFeedbackToast();
    feedbackPromptedHistoryId = '';
    feedbackToastDismissedFor = '';
    return;
  }
  zone.classList.add('open');
  if(!state.feedback_required){
    hideFeedbackToast();
    return;
  }
  const history = state.last_history_entry || {};
  const renderId = String(history.id || 'current');
  if(feedbackPromptedHistoryId !== renderId){
    feedbackVote = '';
    setFeedbackVote('');
    feedbackToastDismissedFor = '';
    document.getElementById('feedbackIssue').value = '';
    document.getElementById('feedbackComment').value = '';
    document.getElementById('feedbackContact').value = '';
    document.getElementById('feedbackStatus').textContent = '';
    feedbackPromptedHistoryId = renderId;
    hideFeedbackToast();
  }
  if(feedbackToastDismissedFor === renderId) return;
  feedbackTimer = setTimeout(() => {
    if(!lastState || !lastState.feedback_required) return;
    if(feedbackPromptedHistoryId !== renderId) return;
    if(feedbackToastDismissedFor === renderId) return;
    showFeedbackToast();
  }, FEEDBACK_TOAST_DELAY_MS);
}
async function submitFeedback(){
  const statusEl = document.getElementById('feedbackStatus');
  const btn = document.getElementById('feedbackSubmitBtn');
  if(statusEl) statusEl.textContent = '';
  if(!feedbackVote){
    if(statusEl) statusEl.textContent = 'Выберите: нравится или не нравится.';
    openFeedbackZone();
    return;
  }
  if(!projectId) return;
  try{
    if(btn) btn.disabled = true;
    const fd = new FormData();
    fd.append('vote', feedbackVote);
    fd.append('issue_type', document.getElementById('feedbackIssue').value || '');
    fd.append('comment', document.getElementById('feedbackComment').value || '');
    fd.append('contact', document.getElementById('feedbackContact').value || '');
    await api(`/api/projects/${projectId}/feedback`, {method:'POST', body: fd});
    if(statusEl) statusEl.textContent = 'Спасибо! Оценка сохранена для обучения.';
    lastState.feedback_required = false;
    hideFeedbackToast();
    dismissFeedbackToast();
  }catch(err){
    if(statusEl) statusEl.textContent = String(err.message || err);
  }finally{
    if(btn) btn.disabled = false;
  }
}
function maybeShowWelcomeTour(){
  try{
    if(localStorage.getItem('niteos_studio_tour_seen') === '1') return;
  }catch(_){}
  setTimeout(() => openStudioTour(), 500);
}
function previewHistory(url){
  const img = document.getElementById('finalImg');
  img.onload = () => syncEditMarkupCanvas();
  img.src = url + (url.includes('?') ? '&' : '?') + 't=' + Date.now();
  clearEditMarkup();
}
async function restoreHistoryVersion(historyId){
  if(!projectId || busy || historyId == null || historyId === '') return;
  try{
    setBusy(true, 'Восстанавливаю версию #' + historyId + ' как активную…');
    const fd = new FormData();
    fd.append('history_id', String(historyId));
    const data = await api(`/api/projects/${projectId}/studio/restore-history`, {method:'POST', body: fd});
    clearEditMarkup();
    await refreshState();
    setBusy(false, data.message || ('Версия #' + historyId + ' активна. Рисуйте и жмите «Отправить».'));
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
function setMarkupEnabled(on){
  editMarkupReady = !!on;
  const canvas = document.getElementById('editMarkupCanvas');
  const stage = document.getElementById('resultStage');
  if(canvas){
    canvas.classList.toggle('hidden', !on);
    canvas.setAttribute('aria-hidden', on ? 'false' : 'true');
  }
  if(stage) stage.classList.toggle('is-editing', !!on);
  if(on) syncEditMarkupCanvas();
  updateEditToolUi();
}
function updateEditToolUi(){
  const brush = document.getElementById('editBrushBtn');
  const eraser = document.getElementById('editEraserBtn');
  const canvas = document.getElementById('editMarkupCanvas');
  const hint = document.getElementById('markupHint');
  const input = document.getElementById('chatInput');
  const toolOn = !!editTool && editMarkupReady;
  if(brush) brush.classList.toggle('active', editTool === 'brush');
  if(eraser) eraser.classList.toggle('active', editTool === 'eraser');
  if(canvas){
    canvas.classList.toggle('tool-on', toolOn);
    canvas.style.cursor = editTool === 'eraser' ? 'cell' : (editTool === 'brush' ? 'crosshair' : 'default');
  }
  syncQuickPromptsForTool();
  if(hint){
    if(editTool === 'eraser'){
      hint.style.display = 'block';
      hint.classList.add('busy');
      hint.textContent = 'Ластик включён: отметьте светильники голубым и выберите вариант в чате (голубые кнопки) или напишите сами.';
    } else if(editTool === 'brush'){
      hint.style.display = 'block';
      hint.classList.add('busy');
      hint.textContent = 'Кисть включена: отметьте зону красным и выберите вариант в чате (красные кнопки) или напишите сами.';
    } else {
      hint.style.display = 'none';
      hint.classList.remove('busy');
    }
  }
  if(input){
    if(editTool === 'eraser'){
      input.placeholder = 'Что убрать? Или нажмите голубую кнопку ниже…';
    } else if(editTool === 'brush'){
      input.placeholder = 'Что сделать в зоне? Или нажмите красную кнопку ниже…';
    } else {
      input.placeholder = 'Что хотите сделать? Например: убери левый / проставь прожектор в зоне…';
    }
  }
}
function syncQuickPromptsForTool(){
  const brushGroup = document.getElementById('quickBrushGroup');
  const eraserGroup = document.getElementById('quickEraserGroup');
  const root = document.getElementById('quickPrompts');
  if(brushGroup) brushGroup.classList.toggle('open', editTool === 'brush');
  if(eraserGroup) eraserGroup.classList.toggle('open', editTool === 'eraser');
  if(!root) return;
  root.querySelectorAll('button[data-tool="any"]').forEach(btn => {
    btn.classList.toggle('dim', !!editTool);
  });
  if(editTool === 'brush' || editTool === 'eraser'){
    try{
      const chatCard = root.closest('.card') || root;
      chatCard.scrollIntoView({behavior:'smooth', block:'nearest'});
    }catch(_){}
  }
}
function toggleEditTool(tool){
  const next = (tool === 'eraser') ? 'eraser' : 'brush';
  const turningOn = editTool !== next;
  editTool = turningOn ? next : null;
  updateEditToolUi();
  if(turningOn){
    const input = document.getElementById('chatInput');
    if(input){
      try{ input.focus({preventScroll:false}); }catch(_){ input.focus(); }
    }
    setBusy(false, editTool === 'eraser'
      ? 'Ластик: отметьте зону и выберите голубой вариант в чате'
      : 'Кисть: отметьте зону и выберите красный вариант в чате');
  }
}
function setEditTool(tool){
  // legacy alias
  toggleEditTool(tool);
}
function updateEditBrushSize(v){
  editBrushSize = Math.max(4, Math.min(48, Number(v) || 16));
}
function getFinalImageLayout(){
  const stage = document.getElementById('resultStage');
  const img = document.getElementById('finalImg');
  if(!stage || !img || !img.naturalWidth || !img.naturalHeight) return null;
  const sw = stage.clientWidth || 1;
  const sh = stage.clientHeight || 1;
  const nw = img.naturalWidth;
  const nh = img.naturalHeight;
  const scale = Math.min(sw / nw, sh / nh);
  const dw = nw * scale;
  const dh = nh * scale;
  const ox = (sw - dw) / 2;
  const oy = (sh - dh) / 2;
  return {sw, sh, nw, nh, dw, dh, ox, oy, scale};
}
function syncEditMarkupCanvas(){
  const canvas = document.getElementById('editMarkupCanvas');
  const layout = getFinalImageLayout();
  if(!canvas || !layout) return;
  canvas.style.left = layout.ox + 'px';
  canvas.style.top = layout.oy + 'px';
  canvas.style.width = layout.dw + 'px';
  canvas.style.height = layout.dh + 'px';
  const w = Math.max(1, Math.round(layout.dw));
  const h = Math.max(1, Math.round(layout.dh));
  if(canvas.width !== w || canvas.height !== h){
    const prev = document.createElement('canvas');
    prev.width = canvas.width; prev.height = canvas.height;
    if(canvas.width && canvas.height){
      prev.getContext('2d').drawImage(canvas, 0, 0);
    }
    canvas.width = w; canvas.height = h;
    if(prev.width && prev.height){
      canvas.getContext('2d').drawImage(prev, 0, 0, w, h);
    }
  }
}
function canvasPoint(e){
  const canvas = document.getElementById('editMarkupCanvas');
  const rect = canvas.getBoundingClientRect();
  const x = (e.clientX - rect.left) * (canvas.width / Math.max(1, rect.width));
  const y = (e.clientY - rect.top) * (canvas.height / Math.max(1, rect.height));
  return {x, y};
}
function editDrawPoint(e, isStart){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !editMarkupReady || !editTool) return;
  const ctx = canvas.getContext('2d');
  const p = canvasPoint(e);
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  ctx.lineWidth = editBrushSize;
  if(editTool === 'eraser'){
    // Cyan = REMOVE luminaires (not destination-out wipe)
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(79,209,197,0.85)';
    ctx.fillStyle = 'rgba(79,209,197,0.85)';
  } else {
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = 'rgba(255,70,70,0.88)';
    ctx.fillStyle = 'rgba(255,70,70,0.88)';
  }
  if(isStart || !editLastPoint){
    ctx.beginPath();
    ctx.arc(p.x, p.y, editBrushSize / 2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.moveTo(editLastPoint.x, editLastPoint.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
  }
  editLastPoint = p;
}
function bindMarkupCanvas(){
  if(markupBound) return;
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return;
  markupBound = true;
  canvas.addEventListener('pointerdown', (e)=>{
    if(!editMarkupReady || !editTool || busy) return;
    editDrawing = true;
    editDrawPoint(e, true);
    canvas.setPointerCapture(e.pointerId);
  });
  canvas.addEventListener('pointermove', (e)=>{
    if(!editMarkupReady || !editTool || !editDrawing) return;
    editDrawPoint(e, false);
  });
  canvas.addEventListener('pointerup', ()=>{ editDrawing=false; editLastPoint=null; });
  canvas.addEventListener('pointerleave', ()=>{ editDrawing=false; editLastPoint=null; });
  window.addEventListener('resize', ()=>{ if(editMarkupReady) syncEditMarkupCanvas(); });
}
function clearEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(canvas){
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);
  }
  editTool = null;
  editDrawing = false;
  editLastPoint = null;
  updateEditToolUi();
}
function markupHasPaint(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !canvas.width || !canvas.height) return false;
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
  for(let i = 3; i < data.length; i += 16){
    if(data[i] > 8) return true;
  }
  return false;
}
async function exportEditAnnotationBlob(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !markupHasPaint()) return null;
  const layout = getFinalImageLayout();
  const out = document.createElement('canvas');
  if(layout){
    out.width = Math.max(1, Math.round(layout.nw));
    out.height = Math.max(1, Math.round(layout.nh));
  } else {
    const maxSide = 1600;
    const sw = canvas.width, sh = canvas.height;
    const scale = Math.min(1, maxSide / Math.max(sw, sh));
    out.width = Math.max(1, Math.round(sw * scale));
    out.height = Math.max(1, Math.round(sh * scale));
  }
  const ctx = out.getContext('2d');
  ctx.clearRect(0, 0, out.width, out.height);
  ctx.drawImage(canvas, 0, 0, out.width, out.height);
  return await new Promise((resolve) => out.toBlob((b) => resolve(b || null), 'image/png'));
}
function resetStudioUi(){
  lastState = {};
  editTool = null;
  editDrawing = false;
  editLastPoint = null;
  feedbackVote = '';
  feedbackPromptedHistoryId = '';
  feedbackToastDismissedFor = '';
  if(feedbackTimer){ clearTimeout(feedbackTimer); feedbackTimer = null; }

  const dropzone = document.getElementById('dropzone');
  if(dropzone) dropzone.classList.remove('has-image', 'dragover');
  const sourceImg = document.getElementById('sourceImg');
  if(sourceImg){ sourceImg.removeAttribute('src'); sourceImg.src = ''; }
  const finalImg = document.getElementById('finalImg');
  if(finalImg){
    finalImg.onload = null;
    finalImg.removeAttribute('src');
    finalImg.src = '';
  }
  clearEditMarkup();
  setMarkupEnabled(false);

  const hist = document.getElementById('historyStrip');
  if(hist) hist.innerHTML = '<div class="muted">История версий появится после генерации</div>';
  const hint = document.getElementById('activeHistoryHint');
  if(hint) hint.textContent = '';
  renderChat([]);

  const chatInput = document.getElementById('chatInput');
  if(chatInput) chatInput.value = '';
  const sourceFile = document.getElementById('sourceFile');
  if(sourceFile) sourceFile.value = '';

  document.getElementById('downloadBtn').disabled = true;
  const copyBtn = document.getElementById('copyFinalBtn');
  if(copyBtn) copyBtn.disabled = true;
  document.getElementById('chatBtn').disabled = !projectId;
  document.getElementById('startBtn').disabled = !projectId;

  const feedbackZone = document.getElementById('feedbackZone');
  if(feedbackZone) feedbackZone.classList.remove('open');
  const toast = document.getElementById('feedbackToast');
  if(toast) toast.classList.remove('open');
  setFeedbackVote('');
  updateEditToolUi();
}
async function createProject(){
  try{
    setBusy(true, 'Создаю новый проект…');
    const data = await api('/api/projects', {method:'POST', body: new URLSearchParams({name:'AI Studio', mode:'dealer'})});
    projectId = data.id || data.project_id || (data.project && (data.project.id || data.project.project_id)) || '';
    if(!projectId) throw new Error('Не удалось создать проект');
    history.replaceState({}, '', '/studio?project=' + projectId);
    document.getElementById('projectLabel').textContent = 'Проект ' + projectId;
    const dealerLink = document.getElementById('dealerLink');
    if(dealerLink) dealerLink.href = '/dealer?project=' + projectId;
    resetStudioUi();
    syncPhotoWarnVisibility();
    setBusy(false, 'Новый проект пустой. Вставьте фото (Ctrl+V) или выберите файл.');
    return projectId;
  }catch(err){
    setError(String(err.message || err));
    busy = false;
    throw err;
  }
}
async function ensureProject(){
  const id = qs().get('project');
  if(id){
    projectId = id;
    document.getElementById('projectLabel').textContent = 'Проект ' + projectId;
    const dealerLink = document.getElementById('dealerLink');
    if(dealerLink) dealerLink.href = '/dealer?project=' + projectId;
    document.getElementById('startBtn').disabled = false;
    await refreshState();
    syncPhotoWarnVisibility();
    return projectId;
  }
  return createProject();
}
async function refreshState(){
  if(!projectId) return;
  const data = await api(`/api/projects/${projectId}/studio/state`);
  applyStudioPayload(data);
  if(data.has_source && !data.has_final) setBusy(false, 'Фото есть. Можно запускать анализ → генерацию.');
  if(!data.has_source) setBusy(false, 'Скопируйте фото и нажмите Ctrl+V — или выберите файл');
}
function fileFromClipboardItem(item){
  if(!item) return null;
  if(item.kind === 'file' && item.type && item.type.startsWith('image/')){
    return item.getAsFile();
  }
  return null;
}
async function uploadSourceFile(file){
  if(!file) return;
  if(!String(file.type || '').startsWith('image/')){
    setError('Нужно изображение (PNG/JPG/WebP), не файл другого типа');
    return;
  }
  try{
    if(!projectId) await ensureProject();
    setBusy(true, 'Загрузка фото…');
    const name = file.name || ('paste_' + Date.now() + '.png');
    const fd = new FormData();
    fd.append('file', file, name);
    await api(`/api/projects/${projectId}/source`, {method:'POST', body: fd});
    const zone = document.getElementById('dropzone');
    const img = document.getElementById('sourceImg');
    img.src = URL.createObjectURL(file);
    zone.classList.add('has-image');
    setBusy(false, 'Фото загружено. Нажмите «Анализ → генерация».');
    document.getElementById('startBtn').disabled = false;
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
const dropzone = document.getElementById('dropzone');
const sourceFile = document.getElementById('sourceFile');
let dropzoneLastTap = 0;
function openSourceFilePicker(){
  sourceFile.click();
}
document.getElementById('pickFileBtn').addEventListener('click', (e) => {
  e.preventDefault();
  openSourceFilePicker();
});
// File dialog only after two taps / double-click on the dropzone (not one).
dropzone.addEventListener('click', (e) => {
  const now = Date.now();
  if(now - dropzoneLastTap < 450){
    dropzoneLastTap = 0;
    e.preventDefault();
    openSourceFilePicker();
    return;
  }
  dropzoneLastTap = now;
});
dropzone.addEventListener('dblclick', (e) => {
  // Second click already opens via the timer above; block native dblclick side-effects.
  e.preventDefault();
});
dropzone.addEventListener('keydown', (e) => {
  if(e.key === 'Enter' || e.key === ' '){ e.preventDefault(); openSourceFilePicker(); }
});
sourceFile.addEventListener('change', async (e) => {
  const file = e.target.files && e.target.files[0];
  if(file) await uploadSourceFile(file);
  sourceFile.value = '';
});
;['dragenter','dragover'].forEach(ev => {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.add('dragover'); });
});
;['dragleave','drop'].forEach(ev => {
  dropzone.addEventListener(ev, (e) => { e.preventDefault(); e.stopPropagation(); dropzone.classList.remove('dragover'); });
});
dropzone.addEventListener('drop', async (e) => {
  const file = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0];
  if(file) await uploadSourceFile(file);
});
async function setFinalFromFile(file){
  if(!projectId || !file) return;
  try{
    setBusy(true, 'Устанавливаю скопированное фото как рабочее…');
    const fd = new FormData();
    fd.append('file', file, file.name || 'pasted_final.png');
    fd.append('note', 'clipboard paste as working final');
    await api(`/api/projects/${projectId}/studio/set-final`, {method:'POST', body: fd});
    clearEditMarkup();
    await refreshState();
    setBusy(false, 'Рабочее фото обновлено. Можно размечать и править.');
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
function pickClipboardImage(e){
  const items = (e.clipboardData && e.clipboardData.items) ? Array.from(e.clipboardData.items) : [];
  for(const item of items){
    const file = fileFromClipboardItem(item);
    if(file) return file;
  }
  if(e.clipboardData && e.clipboardData.files && e.clipboardData.files.length){
    const f = e.clipboardData.files[0];
    if(f && String(f.type || '').startsWith('image/')) return f;
  }
  return null;
}
window.addEventListener('paste', async (e) => {
  const tag = (e.target && e.target.tagName || '').toLowerCase();
  if(tag === 'textarea' || tag === 'input') return;
  const file = pickClipboardImage(e);
  if(!file) return;
  e.preventDefault();
  // If a final already exists, paste becomes the new working render; otherwise source upload.
  if(lastState && lastState.has_final){
    await setFinalFromFile(file);
  } else {
    await uploadSourceFile(file);
  }
});
dropzone.addEventListener('paste', async (e) => {
  e.stopPropagation();
  const file = pickClipboardImage(e);
  if(!file) return;
  e.preventDefault();
  await uploadSourceFile(file);
});
function toggleTip(id){
  document.querySelectorAll('.tip.open').forEach(el => {
    if(el.id !== id) el.classList.remove('open');
  });
  const tip = document.getElementById(id);
  if(tip) tip.classList.toggle('open');
}
document.addEventListener('click', (e) => {
  const t = e.target;
  if(t && (t.closest && t.closest('.tip'))) return;
  document.querySelectorAll('.tip.open').forEach(el => el.classList.remove('open'));
});
function photoCheckStorageKey(){
  return 'niteos_photo_check_ok_' + (projectId || 'none');
}
function hasPhotoCheckPassed(){
  try{ return localStorage.getItem(photoCheckStorageKey()) === '1'; }catch(_){ return false; }
}
function markPhotoCheckPassed(){
  try{ localStorage.setItem(photoCheckStorageKey(), '1'); }catch(_){}
  const soft = document.getElementById('photoSoftWarn');
  if(soft) soft.style.display = 'none';
}
function syncPhotoWarnVisibility(){
  const soft = document.getElementById('photoSoftWarn');
  if(!soft) return;
  soft.style.display = hasPhotoCheckPassed() ? 'none' : '';
}
function openPhotoCheck(){
  document.getElementById('photoCheckModal').classList.add('open');
}
function closePhotoCheck(){
  document.getElementById('photoCheckModal').classList.remove('open');
}
function confirmPhotoCheckAndStart(){
  markPhotoCheckPassed();
  closePhotoCheck();
  runStudioGeneration();
}
async function startStudio(){
  if(!projectId || busy) return;
  if(!(lastState && lastState.has_source) && !document.getElementById('dropzone').classList.contains('has-image')){
    setError('Сначала загрузите фото фасада');
    return;
  }
  // Подсказка о качестве фото — один раз на проект.
  if(hasPhotoCheckPassed()){
    runStudioGeneration();
    return;
  }
  openPhotoCheck();
}
async function runStudioGeneration(){
  if(!projectId || busy) return;
  try{
    setBusy(true, 'Анализ фасада… подбор стиля… генерация…');
    const fd = new FormData();
    const model = localStorage.getItem('niteos_routerai_model') || '';
    if(model) fd.append('routerai_model', model);
    await api(`/api/projects/${projectId}/studio/start`, {method:'POST', body: fd});
    clearEditMarkup();
    await refreshState();
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
async function startStudioLegacy(){
  // kept for safety if anything still calls old name mid-generation
  return runStudioGeneration();
}
async function sendChat(){
  if(!projectId || busy) return;
  const text = (document.getElementById('chatInput').value || '').trim();
  const annotationBlob = await exportEditAnnotationBlob();
  if(!text && !annotationBlob){
    setError('Напишите, что хотите изменить');
    return;
  }
  if(annotationBlob && !text){
    setError('С разметкой нужно описать правку: что убрать или изменить на отмеченных светильниках?');
    const input = document.getElementById('chatInput');
    if(input){
      try{ input.focus(); }catch(_){}
    }
    return;
  }
  try{
    setBusy(true, annotationBlob ? 'Агент правит отмеченные светильники по вашему тексту…' : 'Агент правит результат…');
    const fd = new FormData();
    fd.append('message', text);
    const model = localStorage.getItem('niteos_routerai_model') || '';
    if(model) fd.append('routerai_model', model);
    if(annotationBlob) fd.append('annotation_file', annotationBlob, 'edit_annotation.png');
    await api(`/api/projects/${projectId}/studio/chat`, {method:'POST', body: fd});
    document.getElementById('chatInput').value = '';
    clearEditMarkup();
    await refreshState();
    setBusy(false, 'Правка применена');
  }catch(err){
    setError(String(err.message || err));
    busy = false;
  }
}
function fillChatPrompt(text){
  // Only fill the textarea — never auto-send.
  const input = document.getElementById('chatInput');
  if(!input) return;
  input.value = text || '';
  try{ input.focus(); }catch(_){}
  const box = document.getElementById('statusBox');
  if(box){
    box.classList.remove('busy', 'err');
    box.textContent = 'Текст подставлен. Нажмите «Отправить», когда будете готовы.';
  }
}
// Keep old name as alias without auto-send (in case cached HTML still calls it).
function quickChat(text){
  fillChatPrompt(text);
}
function downloadFinal(){
  if(!projectId) return;
  window.open(`/api/projects/${projectId}/file/output/final_imported_render.png`, '_blank');
}
async function copyFinal(){
  if(!projectId) return;
  try{
    const url = `/api/projects/${projectId}/file/output/final_imported_render.png?t=${Date.now()}`;
    const res = await fetch(url, {credentials:'same-origin'});
    if(!res.ok) throw new Error('Не удалось загрузить изображение');
    const blob = await res.blob();
    if(navigator.clipboard && window.ClipboardItem){
      const type = blob.type || 'image/png';
      await navigator.clipboard.write([new ClipboardItem({[type]: blob})]);
      setBusy(false, 'Результат скопирован в буфер. Можно вставить (Ctrl+V) сюда или в другой проект.');
    } else {
      // Fallback: open image so user can copy manually
      window.open(url, '_blank');
      setBusy(false, 'Открыто в новой вкладке — скопируйте изображение вручную.');
    }
  }catch(err){
    setError('Копирование не удалось: ' + String(err.message || err));
  }
}
bindMarkupCanvas();
ensureProject().then(() => {
  syncPhotoWarnVisibility();
  maybeShowWelcomeTour();
}).catch(err => setError(String(err.message || err)));
</script>
</body>
</html>
"""

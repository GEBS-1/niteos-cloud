
let projectId = null;
let editDrawing = false;
let editLastPoint = null;
let editTool = 'brush';
let editBrushSize = 14;
let editMarkupReady = false;
let historyPreviewUrl = '';
let currentFinalUrl = '';
let promptSaveTimer = null;
let dealerScenarios = [];
let routeraiModels = [];
let isGenerating = false;
let renderLimitBlocked = false;
const ROUTERAI_CLIENT_ALIASES = {
  'openai/gpt-5.5': 'openai/gpt-5-image',
};
let dealerScenarioCategories = [];
let selectedDealerScenarioId = null;
let dealerLegacyRefs = [];
let selectedLegacyRefId = null;
let contactCtaAutoScrolled = false;
let imageUploadBusy = false;
let feedbackRating = 0;
const setStatus = (t) => { document.getElementById('statusText').textContent = t; };
function setFeedbackRating(n){
  feedbackRating = Math.max(1, Math.min(5, Number(n) || 0));
  document.querySelectorAll('#feedbackStars button').forEach((btn, i) => {
    btn.classList.toggle('active', i < feedbackRating);
  });
}
async function submitFeedback(){
  const statusEl = document.getElementById('feedbackStatus');
  const btn = document.getElementById('feedbackSubmitBtn');
  if(statusEl) statusEl.textContent = '';
  try{
    await ensureProject();
    const fd = new FormData();
    fd.append('rating', String(feedbackRating || 0));
    fd.append('comment', (document.getElementById('feedbackComment') || {}).value || '');
    fd.append('contact', (document.getElementById('feedbackContact') || {}).value || '');
    await api(`/api/projects/${projectId}/feedback`, {method:'POST', body:fd});
    if(statusEl) statusEl.textContent = 'Спасибо! Отзыв сохранён.';
    if(btn) btn.disabled = true;
  }catch(err){
    if(statusEl) statusEl.textContent = 'Не удалось отправить: ' + (err.message || err);
  }
}
function scrollToCard(cardId){
  const el = document.getElementById(cardId);
  if(el) el.scrollIntoView({behavior:'smooth', block:'start'});
}
function isElementMostlyInView(el){
  if(!el) return false;
  const r = el.getBoundingClientRect();
  const vh = window.innerHeight || 1;
  const visibleTop = Math.max(0, Math.min(vh, r.bottom) - Math.max(0, r.top));
  const ratio = visibleTop / Math.max(1, r.height);
  return ratio >= 0.55;
}
function nudgeToCard(cardId){
  const el = document.getElementById(cardId);
  if(!el) return;
  if(isTextField(document.activeElement)) return;
  if(isElementMostlyInView(el)) return;
  el.classList.add('next-step');
  el.scrollIntoView({behavior:'smooth', block:'start'});
  setTimeout(()=> el.classList.remove('next-step'), 1600);
}
function shouldAutoScrollToResult(){
  const resultZone = document.getElementById('resultZone');
  if(!resultZone) return false;
  const active = document.activeElement;
  if(active && (active.id === 'editInstruction' || active.closest('#dealerLightMap'))) return false;
  if(isElementMostlyInView(resultZone)) return false;
  return true;
}
function autoScrollToResult(){
  if(!shouldAutoScrollToResult()) return;
  const resultZone = document.getElementById('resultZone');
  if(!resultZone) return;
  resultZone.classList.add('scroll-nudge');
  resultZone.scrollIntoView({behavior:'smooth', block:'start'});
  setTimeout(()=> resultZone.classList.remove('scroll-nudge'), 1800);
}
function clearNextStepHighlight(){
  ['sourceCard','scenariosCard','assignmentCard'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.classList.remove('next-step');
  });
}
function setWorkflow(step, done){
  const setState = (id, state) => {
    const el = document.getElementById(id);
    if(!el) return;
    el.classList.remove('active','done');
    if(state === 'done') el.classList.add('done');
    if(state === 'active') el.classList.add('active');
  };
  const hint = document.getElementById('workflowHint');
  const s1 = !!done.s1, s2 = !!done.s2, s3 = !!done.s3;
  setState('wfS1', s1 ? 'done' : (step === 1 ? 'active' : ''));
  setState('wfS2', s2 ? 'done' : (step === 2 ? 'active' : ''));
  setState('wfS3', s3 ? 'done' : (step === 3 ? 'active' : ''));
  clearNextStepHighlight();
  const nextMap = {1:'sourceCard',2:'scenariosCard',3:'assignmentCard'};
  const nextEl = document.getElementById(nextMap[step] || '');
  if(nextEl) nextEl.classList.add('next-step');
  if(!hint) return;
  if(step === 1) hint.innerHTML = 'Шаг 1: <b>вставьте</b> (Ctrl+V) или <b>загрузите</b> фото фасада.';
  else if(step === 2) hint.innerHTML = 'Шаг 2: выберите <b>сценарий</b> (рекомендуется) — подставит эталон, IES и задание.';
  else if(step === 3) hint.innerHTML = 'Шаг 3: уточните <b>задание</b> и нажмите <b>Начать генерацию</b>.';
}
function updateWorkflowFromProject(p){
  const hasSource = !!p.has_source;
  const hasScenarioOrTemplate = !!(p.dealer_scenario_id || p.dealer_legacy_ref || p.has_style);
  const hasPrompt = !!(p.prompt_preview && String(p.prompt_preview).trim().length > 0);
  const hasFinal = !!p.has_final;
  const done = { s1: hasSource, s2: hasScenarioOrTemplate, s3: hasPrompt };
  if(hasFinal){
    const hint = document.getElementById('workflowHint');
    if(hint) hint.innerHTML = 'Готово: можно <b>Перегенерировать</b>, <b>Скачать</b> или перейти к <b>Доработке</b> ниже.';
    ['wfS1','wfS2','wfS3'].forEach(id => { const el = document.getElementById(id); if(el) el.classList.add('done'); });
    clearNextStepHighlight();
    return;
  }
  let next = 1;
  if(!hasSource) next = 1;
  else if(!hasScenarioOrTemplate) next = 2;
  else next = 3;
  setWorkflow(next, done);
}
function showContactCta(openModal){
  const panel = document.getElementById('contactCtaPanel');
  const modal = document.getElementById('contactCtaModal');
  if(panel) panel.classList.remove('hidden');
  if(openModal && modal){
    modal.classList.add('open');
    contactCtaAutoScrolled = true;
  } else if(panel && !contactCtaAutoScrolled){
    contactCtaAutoScrolled = true;
    setTimeout(() => panel.scrollIntoView({behavior:'smooth', block:'nearest'}), 450);
  }
}
function closeContactCtaModal(){
  const modal = document.getElementById('contactCtaModal');
  if(modal) modal.classList.remove('open');
  const panel = document.getElementById('contactCtaPanel');
  if(panel) setTimeout(() => panel.scrollIntoView({behavior:'smooth', block:'nearest'}), 200);
}
function hideContactCta(){
  const panel = document.getElementById('contactCtaPanel');
  const modal = document.getElementById('contactCtaModal');
  if(panel) panel.classList.add('hidden');
  if(modal) modal.classList.remove('open');
  contactCtaAutoScrolled = false;
}
let helpStepIndex = 0;
let tourActiveTarget = null;
let tourFocusEl = null;
let tourRepositionTimer = null;
let guidedTourMode = false;
let guidedGenerateClicked = false;
let lastProjectState = null;
let guidedAutoAdvanceTimer = null;
const TOUR_CARD_RESERVE = 412;
function setTourDim(el, top, left, width, height){
  if(!el) return;
  if(width <= 0 || height <= 0){ el.style.display = 'none'; return; }
  el.style.display = 'block';
  el.style.top = top + 'px';
  el.style.left = left + 'px';
  el.style.width = width + 'px';
  el.style.height = height + 'px';
}
function hideTourDims(){
  ['tourDimTop','tourDimLeft','tourDimBottom','tourDimGap'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  });
}
function hideWelcomeDims(){
  ['welcomeDimTop','welcomeDimLeft','welcomeDimBottom','welcomeDimGap'].forEach(id => {
    const el = document.getElementById(id);
    if(el) el.style.display = 'none';
  });
}
function positionSpotlightOn(targetEl, spotlightId, dimIds, cardReserve){
  const spotlight = document.getElementById(spotlightId);
  if(!targetEl || !spotlight) return;
  const pad = 8;
  const vw = window.innerWidth;
  const vh = window.innerHeight;
  const contentRight = Math.max(0, vw - (cardReserve || 0));
  const rect = targetEl.getBoundingClientRect();
  const top = Math.max(0, rect.top - pad);
  const left = Math.max(0, rect.left - pad);
  const bottom = Math.min(vh, rect.bottom + pad);
  const right = Math.min(contentRight, rect.right + pad);
  const width = Math.max(0, right - left);
  const height = Math.max(0, bottom - top);
  spotlight.style.display = width > 0 && height > 0 ? 'block' : 'none';
  spotlight.style.left = left + 'px';
  spotlight.style.top = top + 'px';
  spotlight.style.width = width + 'px';
  spotlight.style.height = height + 'px';
  const [topId, leftId, bottomId, gapId] = dimIds;
  setTourDim(document.getElementById(topId), 0, 0, contentRight, top);
  setTourDim(document.getElementById(leftId), top, 0, left, height);
  setTourDim(document.getElementById(bottomId), bottom, 0, contentRight, vh - bottom);
  setTourDim(document.getElementById(gapId), top, right, contentRight - right, height);
}
function positionTourUi(){
  const step = TOUR_STEPS[helpStepIndex];
  const targetEl = document.querySelector(step.focus || step.target);
  positionSpotlightOn(targetEl, 'tourSpotlight', ['tourDimTop','tourDimLeft','tourDimBottom','tourDimGap'], TOUR_CARD_RESERVE);
}
function isWelcomeFromLanding(){
  try{
    return new URLSearchParams(location.search).get('welcome') === '1'
      || sessionStorage.getItem('niteos_from_landing') === '1';
  }catch(_){
    return new URLSearchParams(location.search).get('welcome') === '1';
  }
}
function positionWelcomeTourUi(){
  const btn = document.getElementById('helpBtnPromo');
  const card = document.getElementById('welcomeTourCard');
  if(card){
    card.style.top = '50%';
    card.style.left = '50%';
    card.style.transform = 'translate(-50%,-50%)';
  }
  if(btn){
    btn.classList.add('tour-focus-pulse');
    positionSpotlightOn(btn, 'welcomeSpotlight', ['welcomeDimTop','welcomeDimLeft','welcomeDimBottom','welcomeDimGap'], 0);
  } else {
    hideWelcomeDims();
    const spotlight = document.getElementById('welcomeSpotlight');
    if(spotlight) spotlight.style.display = 'none';
  }
}
function showWelcomeTourPrompt(forceFromLanding){
  const fromLanding = forceFromLanding || isWelcomeFromLanding();
  if(!fromLanding) return;
  const root = document.getElementById('welcomeTourRoot');
  if(!root) return;
  root.classList.add('open');
  positionWelcomeTourUi();
  setTimeout(positionWelcomeTourUi, 200);
  setTimeout(positionWelcomeTourUi, 700);
}
function dismissWelcomeTourPrompt(){
  const root = document.getElementById('welcomeTourRoot');
  if(root) root.classList.remove('open');
  const btn = document.getElementById('helpBtnPromo');
  if(btn) btn.classList.remove('tour-focus-pulse');
  hideWelcomeDims();
  const spotlight = document.getElementById('welcomeSpotlight');
  if(spotlight) spotlight.style.display = 'none';
  try{
    const clean = new URL(location.href);
    clean.searchParams.delete('welcome');
    history.replaceState({}, '', clean.pathname + clean.search + clean.hash);
  }catch(_){}
}
function initWelcomeFromLanding(){
  if(!isWelcomeFromLanding()) return;
  try{ sessionStorage.removeItem('niteos_from_landing'); }catch(_){}
  const run = () => showWelcomeTourPrompt(true);
  setTimeout(run, 500);
  setTimeout(run, 1100);
}
const TOUR_STEPS = [
  {
    id: 'photo',
    target: '#sourceCard',
    focus: '#sourceUploadBtn',
    badge: '1',
    title: 'Шаг 1 — Фото фасада',
    lead: 'Загрузите дневное фото здания. Архитектуру AI не меняет — только добавляет подсветку.',
    waitHint: 'Загрузите фото (кнопка <b>Загрузить</b>, Ctrl+V или перетащите файл) — перейдём к шагу 2 автоматически.',
    actions: [
      'Нажмите <b>Загрузить</b> и выберите файл',
      'Или кликните в область превью и вставьте через <b>Ctrl+V</b>',
      'Можно выбрать из <b>Каталога</b> ранее сохранённое фото'
    ]
  },
  {
    id: 'scenario',
    target: '#scenariosCard',
    focus: '#dealerScenarioGrid .scenario-card',
    badge: '2',
    title: 'Шаг 2 — Сценарий',
    lead: 'Выберите сценарий — подставятся эталон, IES и задание. Это рекомендуемый путь.',
    waitHint: 'Нажмите на любой <b>сценарий</b> в карусели — перейдём к шагу 3 автоматически.',
    actions: [
      'Прокрутите карточки и выберите <b>сценарий</b>',
      'Сценарий подставит эталон + IES + текст задания',
      'Шаблоны решений — только эталон, без IES'
    ]
  },
  {
    id: 'generate',
    target: '#assignmentCard',
    focus: '#generateBtn',
    badge: '3',
    title: 'Шаг 3 — Генерация',
    lead: 'Проверьте задание и запустите визуализацию. Обычно 20–60 секунд.',
    waitHint: 'Нажмите <b>Начать генерацию</b> — дождёмся результата на шаге 4.',
    actions: [
      'При необходимости выберите <b>тип фасада</b>',
      'Можно отредактировать текст задания',
      'Нажмите <b>Начать генерацию</b>'
    ]
  },
  {
    id: 'result',
    target: '#resultZone',
    focus: '#resultStage',
    badge: '4',
    title: 'Шаг 4 — Результат',
    lead: 'Здесь появится ночной рендер. Под ним — светильник, сценарий и IES.',
    waitHint: 'Дождитесь окончания генерации — результат появится в этом блоке.',
    actions: [
      'Можно <b>Скачать</b> PNG или <b>Перегенерировать</b>',
      'Блок «Использовано в этой генерации» — карточка светильника',
      'Ниже — <b>Доработка</b> по текстовому заданию'
    ]
  }
];
function guidedStepComplete(stepIndex, p){
  if(!p) return false;
  const step = TOUR_STEPS[stepIndex];
  if(!step) return false;
  if(step.id === 'photo') return !!p.has_source;
  if(step.id === 'scenario') return !!(p.dealer_scenario_id || p.dealer_legacy_ref);
  if(step.id === 'generate') return !!guidedGenerateClicked;
  if(step.id === 'result') return !!p.has_final;
  return false;
}
function firstIncompleteGuidedStep(p){
  for(let i = 0; i < TOUR_STEPS.length; i++){
    if(!guidedStepComplete(i, p)) return i;
  }
  return TOUR_STEPS.length - 1;
}
function clearTourPulse(){
  if(tourFocusEl){
    tourFocusEl.classList.remove('tour-focus-pulse');
    tourFocusEl = null;
  }
}
function tourActionsHtml(actions){
  if(!actions || !actions.length) return '';
  return `<div class="tour-actions"><div class="label">Куда нажимать</div><ul>${
    actions.map(a => `<li>${a}</li>`).join('')
  }</ul></div>`;
}
function clearTourHighlight(){
  if(tourActiveTarget){
    tourActiveTarget.classList.remove('tour-target-active');
    tourActiveTarget = null;
  }
  clearTourPulse();
}
function renderHelpStep(){
  const step = TOUR_STEPS[helpStepIndex];
  const total = TOUR_STEPS.length;
  const targetEl = document.querySelector(step.target);
  const focusEl = document.querySelector(step.focus || step.target);
  const complete = guidedTourMode && guidedStepComplete(helpStepIndex, lastProjectState);
  document.getElementById('helpStepBadge').textContent = step.badge;
  document.getElementById('helpTitle').textContent = step.title;
  document.getElementById('helpStepCounter').textContent = guidedTourMode
    ? `Интерактивный тур · шаг ${helpStepIndex + 1} из ${total}`
    : `Шаг ${helpStepIndex + 1} из ${total}`;
  const waitHtml = guidedTourMode && !complete && step.waitHint
    ? `<p class="tour-wait-hint">${step.waitHint}</p>` : '';
  document.getElementById('helpBody').innerHTML =
    `<p class="help-lead">${step.lead}</p>${tourActionsHtml(step.actions)}${waitHtml}`;
  document.getElementById('helpDots').innerHTML = TOUR_STEPS.map((_, i) =>
    `<span class="help-dot${i === helpStepIndex ? ' active' : ''}${guidedTourMode ? ' locked' : ''}" title="Шаг ${i + 1}"></span>`
  ).join('');
  const prevBtn = document.getElementById('helpPrevBtn');
  const nextBtn = document.getElementById('helpNextBtn');
  const skipBtn = document.querySelector('.tour-skip');
  if(prevBtn) prevBtn.disabled = guidedTourMode || helpStepIndex === 0;
  if(skipBtn) skipBtn.textContent = guidedTourMode ? 'Выйти из тура' : 'Пропустить';
  if(nextBtn){
    if(guidedTourMode){
      if(helpStepIndex === TOUR_STEPS.length - 1){
        nextBtn.textContent = complete ? 'Готово ✓' : 'Ждём результат…';
        nextBtn.disabled = !complete;
      } else if(helpStepIndex === 2){
        nextBtn.textContent = 'Нажмите «Начать генерацию»';
        nextBtn.disabled = true;
      } else {
        nextBtn.textContent = complete ? 'Далее →' : 'Ждём действие…';
        nextBtn.disabled = !complete;
      }
    } else {
      nextBtn.disabled = false;
      nextBtn.textContent = helpStepIndex === total - 1 ? 'Понятно ✓' : 'Далее →';
    }
  }
  clearTourHighlight();
  clearTourPulse();
  if(targetEl){
    tourActiveTarget = targetEl;
    targetEl.classList.add('tour-target-active');
    targetEl.scrollIntoView({behavior:'smooth', block:'center'});
  }
  if(focusEl && guidedTourMode){
    tourFocusEl = focusEl;
    focusEl.classList.add('tour-focus-pulse');
  }
  clearTimeout(tourRepositionTimer);
  tourRepositionTimer = setTimeout(positionTourUi, 420);
  setTimeout(positionTourUi, 700);
}
function openGuidedTour(){
  dismissWelcomeTourPrompt();
  guidedTourMode = true;
  guidedGenerateClicked = false;
  helpStepIndex = firstIncompleteGuidedStep(lastProjectState || {});
  document.getElementById('tourRoot').classList.add('open');
  document.getElementById('tourCard').classList.add('open');
  renderHelpStep();
}
function openHelp(){ openGuidedTour(); }
function closeHelp(){
  guidedTourMode = false;
  guidedGenerateClicked = false;
  clearTimeout(guidedAutoAdvanceTimer);
  document.getElementById('tourRoot').classList.remove('open');
  document.getElementById('tourCard').classList.remove('open');
  document.getElementById('tourSpotlight').style.display = 'none';
  hideTourDims();
  clearTourHighlight();
  clearTimeout(tourRepositionTimer);
  try{ localStorage.setItem('niteos_tour_seen', '1'); }catch(_){}
}
function prevHelpStep(){
  if(guidedTourMode) return;
  if(helpStepIndex > 0){ helpStepIndex--; renderHelpStep(); }
}
function nextHelpStep(){
  if(helpStepIndex < TOUR_STEPS.length - 1){ helpStepIndex++; renderHelpStep(); }
}
function helpNextAction(){
  if(guidedTourMode){
    if(!guidedStepComplete(helpStepIndex, lastProjectState)) return;
    if(helpStepIndex >= TOUR_STEPS.length - 1){ closeHelp(); return; }
    if(helpStepIndex === 2) return;
    nextHelpStep();
    return;
  }
  if(helpStepIndex >= TOUR_STEPS.length - 1) closeHelp();
  else nextHelpStep();
}
function goHelpStep(index){
  if(guidedTourMode) return;
  if(index < 0 || index >= TOUR_STEPS.length) return;
  helpStepIndex = index;
  renderHelpStep();
}
function checkGuidedTourAdvance(p){
  if(!guidedTourMode || !p) return;
  lastProjectState = p;
  renderHelpStep();
  if(!guidedStepComplete(helpStepIndex, p)) return;
  if(helpStepIndex >= TOUR_STEPS.length - 1) return;
  if(helpStepIndex === 2) return;
  clearTimeout(guidedAutoAdvanceTimer);
  guidedAutoAdvanceTimer = setTimeout(() => {
    if(!guidedTourMode) return;
    if(!guidedStepComplete(helpStepIndex, p)) return;
    if(helpStepIndex >= TOUR_STEPS.length - 1) return;
    if(helpStepIndex === 2) return;
    helpStepIndex++;
    renderHelpStep();
  }, 700);
}
function onTourLayout(){
  if(document.getElementById('welcomeTourRoot')?.classList.contains('open')) positionWelcomeTourUi();
  if(!document.getElementById('tourRoot').classList.contains('open')) return;
  positionTourUi();
}
window.addEventListener('resize', onTourLayout);
window.addEventListener('scroll', onTourLayout, true);
document.addEventListener('keydown', (e) => {
  if(document.getElementById('welcomeTourRoot')?.classList.contains('open')){
    if(e.key === 'Escape') dismissWelcomeTourPrompt();
    return;
  }
  const tour = document.getElementById('tourRoot');
  if(tour && tour.classList.contains('open')){
    if(e.key === 'Escape') closeHelp();
    if(e.key === 'ArrowRight' || e.key === 'Enter') helpNextAction();
    if(e.key === 'ArrowLeft') prevHelpStep();
    return;
  }
});
function showGenOverlay(text){
  document.getElementById('genOverlayText').textContent = text || 'Идёт генерация...';
  document.getElementById('genOverlay').classList.add('open');
}
function hideGenOverlay(){ document.getElementById('genOverlay').classList.remove('open'); }
async function api(path, opts={}) {
  const r = await fetch(path, {credentials:'same-origin', ...opts});
  if (!r.ok) {
    let msg = await r.text();
    try {
      const j = JSON.parse(msg);
      msg = j.detail || msg;
      if (Array.isArray(msg)) msg = msg.map(x => x.msg || String(x)).join(', ');
    } catch(_) {}
    const err = new Error(msg);
    err.status = r.status;
    throw err;
  }
  return await r.json();
}
async function refreshRenderLimit(){
  try {
    const s = await api('/api/visitor/limits');
    if(!s.enabled){
      renderLimitBlocked = false;
      updateGenerateControls(lastProjectState);
      return;
    }
    const el = document.getElementById('renderLimitHint');
    renderLimitBlocked = s.remaining <= 0;
    if(!el) return;
    el.classList.remove('hidden');
    if(renderLimitBlocked){
      el.textContent = `Лимит на сегодня исчерпан (${s.limit} в сутки). Для детальной визуализации позвоните +70123456789.`;
    } else {
      el.textContent = `Осталось генераций сегодня: ${s.remaining} из ${s.limit}`;
    }
    updateGenerateControls(lastProjectState);
  } catch(_) {}
}
function normalizeRouteraiModel(modelId){
  const id = (modelId || '').trim();
  return ROUTERAI_CLIENT_ALIASES[id] || id;
}
function routeraiModelLabel(modelId){
  const item = routeraiModels.find(m => m.id === modelId);
  return item ? item.label : modelId;
}
function updateRouteraiModelHint(){
  const sel = document.getElementById('routeraiModel');
  const hint = document.getElementById('routeraiModelHint');
  const pill = document.getElementById('routeraiModelPill');
  if(!sel || !hint) return;
  const val = sel.value;
  if(!val){
    hint.textContent = sel.options.length <= 1 ? 'Загрузка списка моделей…' : 'Выберите модель.';
    if(pill) pill.classList.add('hidden');
    return;
  }
  hint.textContent = 'Будет использована: ' + routeraiModelLabel(val)
    + (val.includes('gpt-5') ? '. Медленная модель: генерация может занять до 10 минут — не закрывайте страницу.' : '');
  if(pill){
    pill.textContent = val.split('/').pop() || val;
    pill.classList.remove('hidden');
  }
}
function onRouteraiModelChange(){
  const sel = document.getElementById('routeraiModel');
  if(sel && sel.value){
    localStorage.setItem('niteos_routerai_model', sel.value);
  }
  updateRouteraiModelHint();
}
function setRouteraiModel(modelId){
  const sel = document.getElementById('routeraiModel');
  if(!sel || !modelId) return false;
  const normalized = normalizeRouteraiModel(modelId);
  if([...sel.options].some(o => o.value === normalized)){
    sel.value = normalized;
    localStorage.setItem('niteos_routerai_model', normalized);
    updateRouteraiModelHint();
    return true;
  }
  return false;
}
function updateGenerateControls(p){
  const btn = document.getElementById('generateBtn');
  const reason = document.getElementById('generateBlockReason');
  if(!btn) return;
  const state = p || lastProjectState || {};
  const hasSource = !!state.has_source;
  const promptEl = document.getElementById('prompt');
  const hasPrompt = !!((promptEl && promptEl.value.trim()) || (state.prompt || '').trim());
  let blocked = '';
  if(isGenerating){
    btn.disabled = true;
    btn.classList.add('is-busy');
  } else if(renderLimitBlocked){
    btn.disabled = true;
    blocked = 'Дневной лимит генераций исчерпан.';
  } else if(!hasSource){
    btn.disabled = true;
    blocked = 'Сначала загрузите фото фасада (шаг 1).';
  } else if(!hasPrompt){
    btn.disabled = true;
    blocked = 'Выберите сценарий или введите задание.';
  } else {
    btn.disabled = false;
    btn.classList.remove('is-busy');
  }
  if(reason){
    if(blocked && !isGenerating){
      reason.textContent = blocked;
      reason.classList.remove('hidden');
    } else {
      reason.classList.add('hidden');
    }
  }
}
async function createProject(){
  const fd = new FormData();
  fd.append('name', 'Cloud project');
  fd.append('mode', 'dealer');
  const p = await api('/api/projects', {method:'POST', body:fd});
  projectId = p.id;
  document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  setStatus('Проект создан');
  refreshProjects();
  refresh();
}
async function toggleProjects(){
  const panel = document.getElementById('projectsPanel');
  panel.classList.toggle('open');
  if(panel.classList.contains('open')) await refreshProjects();
}
async function refreshProjects(){
  const projects = await api('/api/projects');
  const panel = document.getElementById('projectsPanel');
  if(!projects.length){
    panel.innerHTML = '<div class="muted">История пока пустая</div>';
    return;
  }
  panel.innerHTML = projects.map(projectCard).join('');
}
function esc(value){
  return String(value || '').replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]));
}
function projectCard(p){
  const status = esc(p.status || 'created');
  const updated = esc(p.updated_at || p.created_at || '');
  const prompt = esc(p.prompt_preview || 'Prompt не сохранен');
  const result = p.has_final ? 'финал есть' : 'финала нет';
  const light = p.has_light_map ? 'карта есть' : 'карты нет';
  return `<div class="project-card">
    <div class="title">${esc(p.name || 'Проект')} / ${esc(p.id)}</div>
    <div class="meta">Статус: ${status}<br>Обновлен: ${updated}<br>Фото: ${p.has_source ? 'есть' : 'нет'} · IES: ${p.ies_count || 0} · Style: ${p.has_style ? 'есть' : 'нет'}<br>${light} · ${result}<br>Задание: ${prompt}</div>
    <button class="secondary" onclick="openProject('${esc(p.id)}')">Открыть</button>
  </div>`;
}
async function openProject(id){
  const p = await api(`/api/projects/${id}`);
  projectId = id;
  document.getElementById('projectInfo').textContent = `Проект: ${projectId}`;
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  if(p.routerai_model) setRouteraiModel(p.routerai_model);
  setStatus('Проект открыт');
  refreshPipelineLog(false);
  refresh();
}
async function ensureProject(){ if(!projectId) await createProject(); }
function chooseFile(inputId){
  const input = document.getElementById(inputId);
  input.value = '';
  input.click();
}
function togglePanel(panelId){
  refreshLibrary();
  document.getElementById(panelId).classList.toggle('open');
}
function isClipboardImageItem(item){
  if(!item || item.kind !== 'file') return false;
  const type = (item.type || '').toLowerCase();
  return !type || type.startsWith('image/');
}
function imageFromClipboard(event){
  const items = event.clipboardData && event.clipboardData.items;
  if(!items) return null;
  for(const item of items){
    if(!isClipboardImageItem(item)) continue;
    const file = item.getAsFile();
    if(file && file.size > 0) return file;
  }
  return null;
}
function imageFromDataTransfer(dt){
  if(!dt) return null;
  if(dt.files && dt.files.length){
    for(const f of dt.files){
      const type = (f.type || '').toLowerCase();
      if(!type || type.startsWith('image/')) return f;
    }
  }
  if(dt.items){
    for(const item of dt.items){
      if(!isClipboardImageItem(item)) continue;
      const file = item.getAsFile();
      if(file && file.size > 0) return file;
    }
  }
  return null;
}
function namedImageFile(file, prefix){
  const name = (file.name || '').trim();
  if(name && name !== 'image.png' && name !== 'blob') return file;
  const ext = ((file.type || 'image/png').split('/')[1] || 'png').replace('jpeg', 'jpg');
  return new File([file], `${prefix}-${Date.now()}.${ext}`, {type: file.type || 'image/png'});
}
async function uploadSource(file){
  if(imageUploadBusy) return;
  await ensureProject();
  const f = file || document.getElementById('sourceFile').files[0];
  if(!f) return;
  imageUploadBusy = true;
  try{
    const fd = new FormData();
    fd.append('file', namedImageFile(f, 'pasted-source'));
    await api(`/api/projects/${projectId}/source`, {method:'POST', body:fd});
    setStatus('Фото загружено и сохранено в каталог');
    refresh();
    setTimeout(()=> nudgeToCard('scenariosCard'), 250);
  }catch(err){
    setStatus('Ошибка загрузки фото: ' + err.message);
  }finally{
    imageUploadBusy = false;
  }
}
async function uploadIes(){
  await ensureProject();
  const fd = new FormData(); for(const f of document.getElementById('iesFiles').files) fd.append('files', f);
  await api(`/api/projects/${projectId}/ies`, {method:'POST', body:fd}); setStatus('IES загружены и сохранены в каталог'); refresh();
  setTimeout(()=> nudgeToCard('scenariosCard'), 250);
}
async function uploadStyle(file){
  if(imageUploadBusy) return;
  await ensureProject();
  const f = file || document.getElementById('styleFile').files[0];
  if(!f) return;
  imageUploadBusy = true;
  try{
    const fd = new FormData();
    fd.append('file', namedImageFile(f, 'pasted-style'));
    await api(`/api/projects/${projectId}/style`, {method:'POST', body:fd});
    setStatus('Style загружен и сохранён в каталог');
    refresh();
    setTimeout(()=> nudgeToCard('assignmentCard'), 250);
  }catch(err){
    setStatus('Ошибка загрузки эталона: ' + err.message);
  }finally{
    imageUploadBusy = false;
  }
}
function isTextField(el){
  if(!el) return false;
  if(el.isContentEditable) return true;
  const tag = el.tagName;
  if(tag === 'TEXTAREA') return true;
  if(tag === 'INPUT'){
    const t = (el.type || 'text').toLowerCase();
    return !['button','checkbox','file','radio','range','submit','reset','color','hidden'].includes(t);
  }
  return false;
}
function pasteTargetFromFocus(){
  const active = document.activeElement;
  if(active && (active.id === 'stylePreviewBox' || active.closest('#stylePreviewBox'))) return 'style';
  if(active && (active.id === 'sourcePreviewBox' || active.closest('#sourceCard'))) return 'source';
  return 'source';
}
async function handlePastedImage(event, forcedTarget){
  const file = imageFromClipboard(event);
  if(!file) return false;
  event.preventDefault();
  event.stopPropagation();
  const target = forcedTarget || pasteTargetFromFocus();
  try{
    if(target === 'style') await uploadStyle(file);
    else await uploadSource(file);
  }catch(err){
    setStatus('Ошибка загрузки изображения: ' + err.message);
  }
  return true;
}
async function handleDroppedImage(event, target){
  const file = imageFromDataTransfer(event.dataTransfer);
  if(!file) return;
  event.preventDefault();
  event.currentTarget.classList.remove('paste-hover');
  try{
    if(target === 'style') await uploadStyle(file);
    else await uploadSource(file);
  }catch(err){
    setStatus('Ошибка загрузки изображения: ' + err.message);
  }
}
function setupImagePasteZones(){
  document.addEventListener('paste', async (event) => {
    if(isTextField(document.activeElement)) return;
    if(event.target && event.target.closest && event.target.closest('.paste-zone')) return;
    await handlePastedImage(event);
  });
  for(const [id, target] of [['sourcePreviewBox','source'], ['stylePreviewBox','style']]){
    const box = document.getElementById(id);
    if(!box) continue;
    box.addEventListener('click', () => box.focus());
    box.addEventListener('paste', (event) => { void handlePastedImage(event, target); });
    box.addEventListener('dragover', (event) => { event.preventDefault(); box.classList.add('paste-hover'); });
    box.addEventListener('dragleave', () => box.classList.remove('paste-hover'));
    box.addEventListener('drop', (event) => handleDroppedImage(event, target));
  }
}
async function savePrompt(){
  await ensureProject();
  const fd = new FormData();
  fd.append('prompt', document.getElementById('prompt').value);
  fd.append('facade_mode', document.getElementById('facadeMode').value);
  await api(`/api/projects/${projectId}/prompt`, {method:'POST', body:fd}); setStatus('Задание сохранено'); refreshPipelineLog(false);
}
async function enhancePrompt(){
  await ensureProject();
  await savePrompt();
  const p = await api(`/api/projects/${projectId}/enhance-prompt`, {method:'POST'});
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  setStatus('Задание сжато: короткая и четкая логика для AI');
  refreshPipelineLog(true);
}
function schedulePromptSave(){
  clearTimeout(promptSaveTimer);
  promptSaveTimer = setTimeout(() => { savePrompt().catch(()=>{}); }, 700);
}
async function packageOnly(){
  await ensureProject();
  await savePrompt();
  showGenOverlay('Подготавливаем карту света и промпт...');
  try{
    await api(`/api/projects/${projectId}/package`, {method:'POST'});
    setStatus('Пакет готов — смотрите Артефакты и Журнал pipeline');
    refresh(); refreshPipelineLog(true);
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    hideGenOverlay();
  }
}
async function loadRouterModels(){
  const sel = document.getElementById('routeraiModel');
  try{
    const data = await api('/api/routerai-models');
    routeraiModels = data.models || [];
    if(!sel) return;
    if(!routeraiModels.length){
      sel.innerHTML = '<option value="">Модели недоступны</option>';
      updateRouteraiModelHint();
      return;
    }
    const keep = sel.value;
    sel.innerHTML = routeraiModels.map(m =>
      `<option value="${esc(m.id)}">${esc(m.label)}</option>`
    ).join('');
    const saved = normalizeRouteraiModel(
      keep || localStorage.getItem('niteos_routerai_model') || data.default || ''
    );
    if(!setRouteraiModel(saved) && data.default){
      setRouteraiModel(data.default);
    }
    updateRouteraiModelHint();
  }catch(err){
    if(sel) sel.innerHTML = '<option value="">Ошибка загрузки моделей</option>';
    updateRouteraiModelHint();
    console.warn('routerai models', err);
  }
}
async function loadDealerTemplates(){
  const scData = await api('/api/client-scenarios');
  dealerScenarios = scData.scenarios || [];
  dealerScenarioCategories = scData.categories || [];
  dealerLegacyRefs = [];
  renderDealerScenarioGrid();
  if(guidedTourMode && helpStepIndex === 1) renderHelpStep();
}
function renderLegacyGroup(){
  return '';
}
function renderDealerScenarioGrid(){
  const grid = document.getElementById('dealerScenarioGrid');
  const items = dealerScenarios.map(s => {
    const thumb = s.has_preview
      ? `<img src="/api/client-scenarios/${s.id}/preview?t=${Date.now()}" alt="">`
      : '<div class="muted" style="font-size:10px;padding:8px">Нет превью</div>';
    return `<div class="scenario-card ${selectedDealerScenarioId===s.id?'selected':''}" onclick="selectDealerScenario('${s.id}')">
      <div class="thumb">${thumb}</div>
      <div class="title">${esc(s.name)}</div>
      <div class="desc">${esc(s.description)}</div>
    </div>`;
  }).join('');
  grid.innerHTML = items
    ? `<div class="category-row"><div class="scroll-hint">Варианты подсветки · 5 в ряд, до 2 строк — дальше прокрутка вниз</div><div class="scenario-catalog-wrap"><div class="scenario-catalog-grid">${items}</div></div></div>`
    : '<div class="muted">Шаблоны не найдены</div>';
}
async function pickLegacyRef(id, libraryPath, name){
  await ensureProject();
  selectedLegacyRefId = id;
  selectedDealerScenarioId = null;
  const fd = new FormData();
  fd.append('library_path', libraryPath);
  fd.append('name', name || id);
  fd.append('template_id', id);
  await api(`/api/projects/${projectId}/dealer-legacy-template`, {method:'POST', body:fd});
  document.getElementById('dealerScenarioStatus').textContent = `Шаблон: ${name || id}`;
  document.getElementById('styleName').textContent = 'Эталон применён';
  renderDealerScenarioGrid();
  setStatus('Шаблон решения применён — эталон и IES подставлены');
  refresh();
  setTimeout(()=> nudgeToCard('assignmentCard'), 250);
}
async function selectDealerScenario(id){
  await ensureProject();
  selectedDealerScenarioId = id;
  selectedLegacyRefId = null;
  const fd = new FormData();
  fd.append('scenario_id', id);
  const p = await api(`/api/projects/${projectId}/dealer-scenario`, {method:'POST', body:fd});
  if(p.prompt) document.getElementById('prompt').value = p.prompt;
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  document.getElementById('dealerScenarioStatus').textContent = p.dealer_scenario_name
    ? `Выбран: ${p.dealer_scenario_name}${p.dealer_product_name ? ' · ' + p.dealer_product_name : ''}`
    : 'Сценарий применён';
  renderDealerScenarioGrid();
  setStatus('Сценарий применён — эталон, IES и задание обновлены');
  refresh();
  setTimeout(()=> nudgeToCard('assignmentCard'), 250);
}
async function generateVisualization(){
  await ensureProject();
  const btn = document.getElementById('generateBtn');
  if(isGenerating || (btn && btn.disabled)) return;
  if(guidedTourMode){
    guidedGenerateClicked = true;
    if(helpStepIndex < 3){
      helpStepIndex = 3;
      renderHelpStep();
    }
  }
  const fd = new FormData();
  fd.append('prompt', document.getElementById('prompt').value);
  fd.append('facade_mode', document.getElementById('facadeMode').value);
  const modelSel = document.getElementById('routeraiModel');
  if(!modelSel || !modelSel.value){
    setStatus('Выберите модель генерации.');
    return;
  }
  fd.append('routerai_model', modelSel.value);
  localStorage.setItem('niteos_routerai_model', modelSel.value);
  document.getElementById('resultZone').classList.remove('empty');
  const btnLabel = document.getElementById('generateBtnLabel');
  const prevLabel = btnLabel ? btnLabel.textContent : 'Начать генерацию';
  isGenerating = true;
  updateGenerateControls(lastProjectState);
  if(btnLabel) btnLabel.textContent = 'Генерация…';
  showGenOverlay('Создаём ночную визуализацию по фото и промпту. Обычно 20–60 секунд...');
  try{
    await api(`/api/projects/${projectId}/render`, {method:'POST', body:fd});
    setStatus('Визуализация готова');
    historyPreviewUrl = '';
    refreshRenderLimit();
    refresh(); refreshPipelineLog(true);
    setTimeout(()=> autoScrollToResult(), 320);
  }catch(err){
    if(err.status === 429){
      setStatus(err.message);
      refreshRenderLimit();
    } else {
      setStatus('Ошибка: ' + err.message);
    }
  }finally{
    isGenerating = false;
    if(btnLabel) btnLabel.textContent = prevLabel;
    updateGenerateControls(lastProjectState);
    hideGenOverlay();
  }
}
async function editRender(){
  await ensureProject();
  const instruction = document.getElementById('editInstruction').value.trim();
  if(!instruction){ setStatus('Напишите, что изменить.'); return; }
  const fd = new FormData();
  fd.append('instruction', instruction);
  const annotation = exportEditComposite();
  if(annotation) fd.append('annotation', annotation);
  showGenOverlay('Отправлена доработка результата...');
  try{
    await api(`/api/projects/${projectId}/edit`, {method:'POST', body:fd});
    clearEditMarkup();
    setStatus('Доработанный результат готов');
    historyPreviewUrl = '';
    refresh(); refreshPipelineLog(true);
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }finally{
    hideGenOverlay();
  }
}
async function importExisting(){
  const data = await api('/api/library-import-existing', {method:'POST'});
  setStatus('Импорт в каталог: '+JSON.stringify(data.imported)); refreshLibrary();
}
async function addFromLibrary(kind, relativePath){
  await ensureProject();
  const fd = new FormData(); fd.append('relative_path', relativePath);
  await api(`/api/projects/${projectId}/library/${kind}`, {method:'POST', body:fd});
  setStatus('Добавлено в проект из каталога'); refresh();
}
function stepTitle(step){
  const map = {
    render_start: '1. Старт рендера',
    dealer_scenario_applied: 'Сценарий применён',
    dealer_legacy_template_applied: 'Шаблон решения применён',
    dealer_style_ref_applied: 'Референс применён',
    packager_done: '2. Пакетер (опционально)',
    prompt_prepared: '2. Промпт для RouterAI',
    prompt_selected: '3. Промпт для отправки в API',
    routerai_render: '3. Запрос в RouterAI (рендер)',
    enhance_prompt: 'Улучшение задания',
    edit_start: '1. Старт доработки',
    routerai_edit: '2. Запрос в RouterAI (доработка)',
    upload_source: 'Загрузка фото',
    upload_ies: 'Загрузка IES',
    upload_style: 'Загрузка style',
    save_prompt: 'Сохранение задания',
    render_error: 'Ошибка рендера',
    edit_error: 'Ошибка доработки',
    package_done: 'Пакетирование',
    package_error: 'Ошибка пакетирования',
  };
  return map[step] || step;
}
function formatLogEntry(entry){
  const lines = [];
  const payload = {...entry};
  const step = payload.step || 'event';
  delete payload.step;
  delete payload.ts;
  if(payload.user_prompt !== undefined && payload.gemini_prompt !== undefined){
    lines.push('Исходное задание:\\n' + payload.user_prompt);
    if(payload.chatgpt_prompt) lines.push('\\nПромпт для AI (04, русский):\\n' + payload.chatgpt_prompt);
    if(payload.gemini_prompt) lines.push('\\nПромпт Gemini (05):\\n' + payload.gemini_prompt);
    if(payload.ies_summary) lines.push('\\nIES-сводка:\\n' + payload.ies_summary);
    delete payload.user_prompt; delete payload.gemini_prompt; delete payload.chatgpt_prompt; delete payload.ies_summary; delete payload.equipment_draft;
  }
  if(payload.before !== undefined && payload.after !== undefined){
    lines.push('Было:\\n' + payload.before + '\\n\\nСтало:\\n' + payload.after);
    delete payload.before; delete payload.after;
  }
  if(payload.prompt_file){
    lines.push('Файл промпта: ' + payload.prompt_file);
    delete payload.prompt_file;
  }
  if(payload.prompt !== undefined && step.includes('routerai')){
    lines.push('Текст запроса:\\n' + payload.prompt);
    if(payload.images) lines.push('\\nИзображения:\\n' + JSON.stringify(payload.images, null, 2));
    if(payload.model) lines.push('\\nМодель: ' + payload.model);
    if(payload.image_config) lines.push('Параметры image: ' + JSON.stringify(payload.image_config));
    if(payload.response_summary) lines.push('\\nОтвет API:\\n' + JSON.stringify(payload.response_summary, null, 2));
    delete payload.prompt; delete payload.images; delete payload.model; delete payload.image_config; delete payload.response_summary; delete payload.modalities; delete payload.endpoint; delete payload.prompt_chars; delete payload.output; delete payload.http_status;
  }
  const rest = Object.keys(payload).length ? '\\n' + JSON.stringify(payload, null, 2) : '';
  const body = (lines.join('\\n') + rest).trim() || JSON.stringify(entry, null, 2);
  return `<div class="log-entry"><div class="head">${esc(entry.ts || '')} · ${esc(stepTitle(step))}</div><pre>${esc(body)}</pre></div>`;
}
async function refreshPipelineLog(openPanel){
  const logBtn = document.getElementById('downloadLogBtn');
  if(!projectId){
    document.getElementById('pipelineLogPanel').innerHTML = '<div class="muted">Сначала создайте или откройте проект.</div>';
    if(logBtn) logBtn.style.display = 'none';
    return;
  }
  const data = await api(`/api/projects/${projectId}/pipeline-log`);
  const entries = data.entries || [];
  if(logBtn) logBtn.style.display = entries.length ? 'inline-block' : 'none';
  if(!entries.length){
    document.getElementById('pipelineLogPanel').innerHTML = '<div class="muted">Журнал пуст. Запустите рендер или загрузите данные.</div>';
    return;
  }
  document.getElementById('pipelineLogPanel').innerHTML = entries.slice().reverse().map(formatLogEntry).join('');
  if(openPanel) document.getElementById('pipelineLogPanel').classList.add('open');
}
function togglePipelineLog(){
  const panel = document.getElementById('pipelineLogPanel');
  const willOpen = !panel.classList.contains('open');
  panel.classList.toggle('open');
  if(willOpen) refreshPipelineLog(false);
}
function downloadPipelineLog(){
  if(!projectId) return;
  window.open(`/api/projects/${projectId}/pipeline-log/download`, '_blank');
}
function libItem(kind, file){
  const urlPath = file.relative_path.split('/').map(encodeURIComponent).join('/');
  const safePath = file.relative_path.replaceAll("'","\\'");
  let preview;
  if(kind === 'ies' && file.has_photo){
    preview = `<img src="/api/library/ies/photo/${urlPath}?t=${Date.now()}" alt="">`;
  } else if(kind !== 'ies'){
    preview = `<img src="/api/library/${kind}/file/${urlPath}?t=${Date.now()}">`;
  } else {
    preview = `<div class="muted">IES</div>`;
  }
  const extraClass = (kind === 'ies' && file.has_photo) ? ' lib-ies-photo' : '';
  return `<div class="lib-item${extraClass}">${preview}<div class="name" title="${file.relative_path}">${file.name}</div><button onclick="addFromLibrary('${kind}','${safePath}')">В проект</button></div>`;
}
function renderUsedIesCard(item){
  const rel = (item.relative_path || item.name || '').split('/').map(encodeURIComponent).join('/');
  const iesUrl = rel ? `/api/projects/${projectId}/file/ies/${rel}` : '';
  let photo = '';
  if(item.has_photo && rel){
    photo = `<img src="/api/projects/${projectId}/ies-photo/${rel}?t=${Date.now()}" alt="">`;
  } else if(item.product_id){
    photo = `<img src="/api/client-products/${encodeURIComponent(item.product_id)}/preview?t=${Date.now()}" alt="">`;
  } else {
    photo = `<div class="ph">Нет фото</div>`;
  }
  const product = item.product_name || item.product_short || 'Светильник';
  const iesName = item.name || '';
  const dl = iesUrl
    ? `<a class="dl" href="${iesUrl}" target="_blank" rel="noopener">Скачать IES</a>`
    : '';
  return `<div class="render-product-card">${photo}<div class="info"><div class="product">${esc(product)}</div><div class="ies">${esc(iesName)}</div>${dl}</div></div>`;
}
function renderUsedIesCards(p, iesFiles){
  const fromMeta = p.render_ies_items || [];
  const names = p.render_ies_files || [];
  const items = fromMeta.length ? fromMeta : names.map(name => {
    const file = (iesFiles || []).find(f => f.name === name);
    return {
      name,
      relative_path: file?.relative_path || name,
      has_photo: !!file?.has_photo,
      product_name: p.render_product_name || '',
      product_id: p.render_product_id || '',
    };
  });
  return items.map(renderUsedIesCard).join('');
}
function renderIesPreview(iesFiles){
  const row = document.getElementById('iesPreviewRow');
  if(!row) return;
  const withPhoto = (iesFiles || []).filter(f => f.has_photo);
  if(!withPhoto.length){
    row.classList.add('hidden');
    row.innerHTML = '';
    return;
  }
  row.classList.remove('hidden');
  row.innerHTML = withPhoto.map(f => {
    const url = `/api/projects/${projectId}/ies-photo/${f.relative_path.split('/').map(encodeURIComponent).join('/')}?t=${Date.now()}`;
    return `<div class="ies-preview-card" title="${esc(f.name)}">
      <img src="${url}" alt="">
      <div class="cap">${esc(f.name)}</div>
    </div>`;
  }).join('');
}
function historyKindLabel(kind){
  if(kind === 'edit') return 'Доработка';
  if(kind === 'regenerate') return 'Перегенерация';
  return 'Генерация';
}
function renderRenderHistory(history){
  const panel = document.getElementById('renderHistoryPanel');
  const strip = document.getElementById('renderHistoryStrip');
  if(!panel || !strip) return;
  const items = history || [];
  if(!items.length){
    panel.classList.add('hidden');
    strip.innerHTML = '';
    return;
  }
  panel.classList.remove('hidden');
  strip.innerHTML = items.map((h, idx) => {
    const fname = (h.file || '').replace(/^history\//, '');
    const url = `/api/projects/${projectId}/file/history/${encodeURIComponent(fname)}`;
    const active = (!historyPreviewUrl && idx === items.length - 1) || historyPreviewUrl === url ? ' active' : '';
    return `<button type="button" class="render-history-item${active}" onclick="previewHistoryItem('${esc(url)}', ${h.id})">
      <img src="${url}?t=${Date.now()}" alt="">
      <span>${esc(historyKindLabel(h.kind))} #${h.id}</span>
    </button>`;
  }).join('');
}
function previewHistoryItem(url, id){
  historyPreviewUrl = url;
  const img = document.getElementById('finalImg');
  if(img) img.src = url + '?t=' + Date.now();
  setStatus(`Просмотр версии #${id} из истории. Текущий финал не изменён.`);
  if(lastProjectState && lastProjectState.render_history){
    renderRenderHistory(lastProjectState.render_history);
  }
}
function setEditTool(tool){
  editTool = tool === 'eraser' ? 'eraser' : 'brush';
  const brushBtn = document.getElementById('editBrushBtn');
  const eraserBtn = document.getElementById('editEraserBtn');
  if(brushBtn) brushBtn.classList.toggle('active', editTool === 'brush');
  if(eraserBtn) eraserBtn.classList.toggle('active', editTool === 'eraser');
  const canvas = document.getElementById('editMarkupCanvas');
  if(canvas) canvas.style.cursor = editTool === 'eraser' ? 'cell' : 'crosshair';
}
function updateEditBrushSize(v){
  editBrushSize = Math.max(4, Math.min(48, Number(v) || 14));
}
function setupEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  const stage = document.getElementById('editMarkupStage');
  if(!canvas || !stage) return;
  const resize = () => {
    const rect = stage.getBoundingClientRect();
    const dpr = window.devicePixelRatio || 1;
    const old = exportEditMarkupLayer();
    canvas.width = Math.max(1, Math.round(rect.width * dpr));
    canvas.height = Math.max(1, Math.round(rect.height * dpr));
    const ctx = canvas.getContext('2d');
    ctx.setTransform(1, 0, 0, 1, 0, 0);
    ctx.scale(dpr, dpr);
    if(old) restoreEditMarkupLayer(old);
  };
  window.addEventListener('resize', resize);
  setTimeout(resize, 80);
  canvas.addEventListener('pointerdown', (e)=>{ if(!editMarkupReady) return; editDrawing=true; editDrawPoint(e, true); canvas.setPointerCapture(e.pointerId); });
  canvas.addEventListener('pointermove', (e)=>{ if(!editMarkupReady || !editDrawing) return; editDrawPoint(e, false); });
  canvas.addEventListener('pointerup', ()=>{ editDrawing=false; editLastPoint=null; });
  canvas.addEventListener('pointerleave', ()=>{ editDrawing=false; editLastPoint=null; });
}
function editCanvasPoint(e){
  const canvas = document.getElementById('editMarkupCanvas');
  const rect = canvas.getBoundingClientRect();
  return {x:e.clientX-rect.left, y:e.clientY-rect.top};
}
function editDrawPoint(e, start){
  const canvas = document.getElementById('editMarkupCanvas');
  const ctx = canvas.getContext('2d');
  const p = editCanvasPoint(e);
  ctx.lineWidth = editBrushSize;
  ctx.lineCap = 'round';
  ctx.lineJoin = 'round';
  if(editTool === 'eraser'){
    ctx.globalCompositeOperation = 'destination-out';
    ctx.strokeStyle = 'rgba(0,0,0,1)';
  } else {
    ctx.globalCompositeOperation = 'source-over';
    ctx.strokeStyle = '#ff2b2b';
  }
  if(start || !editLastPoint){
    editLastPoint = p;
    ctx.beginPath();
    ctx.moveTo(p.x, p.y);
    ctx.lineTo(p.x + 0.01, p.y + 0.01);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(editLastPoint.x, editLastPoint.y);
    ctx.lineTo(p.x, p.y);
    ctx.stroke();
    editLastPoint = p;
  }
  ctx.globalCompositeOperation = 'source-over';
}
function loadEditMarkupImage(url){
  const panel = document.getElementById('editMarkupPanel');
  const img = document.getElementById('editMarkupImg');
  if(!panel || !img) return;
  if(!url){
    panel.classList.add('hidden');
    editMarkupReady = false;
    img.removeAttribute('src');
    clearEditMarkup();
    return;
  }
  panel.classList.remove('hidden');
  img.onload = () => {
    editMarkupReady = true;
    const stage = document.getElementById('editMarkupStage');
    const canvas = document.getElementById('editMarkupCanvas');
    if(stage && canvas){
      const rect = stage.getBoundingClientRect();
      const dpr = window.devicePixelRatio || 1;
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      const ctx = canvas.getContext('2d');
      ctx.setTransform(1, 0, 0, 1, 0, 0);
      ctx.scale(dpr, dpr);
      ctx.clearRect(0, 0, rect.width, rect.height);
    }
  };
  img.src = url;
}
function clearEditMarkup(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return;
  const ctx = canvas.getContext('2d');
  const rect = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, rect.width, rect.height);
  editLastPoint = null;
}
function exportEditMarkupLayer(){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas) return '';
  const ctx = canvas.getContext('2d');
  const data = ctx.getImageData(0,0,canvas.width,canvas.height).data;
  for(let i=3;i<data.length;i+=4){ if(data[i] > 0) return canvas.toDataURL('image/png'); }
  return '';
}
function restoreEditMarkupLayer(dataUrl){
  const canvas = document.getElementById('editMarkupCanvas');
  if(!canvas || !dataUrl) return;
  const img = new Image();
  img.onload = () => {
    const ctx = canvas.getContext('2d');
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    ctx.drawImage(img, 0, 0, rect.width, rect.height);
  };
  img.src = dataUrl;
}
function exportEditComposite(){
  const baseImg = document.getElementById('editMarkupImg');
  const overlay = document.getElementById('editMarkupCanvas');
  if(!baseImg || !overlay || !baseImg.naturalWidth) return '';
  const markup = exportEditMarkupLayer();
  if(!markup) return '';
  const stage = document.getElementById('editMarkupStage');
  const rect = stage ? stage.getBoundingClientRect() : {width: baseImg.clientWidth, height: baseImg.clientHeight};
  const w = Math.max(1, Math.round(rect.width));
  const h = Math.max(1, Math.round(rect.height));
  const out = document.createElement('canvas');
  out.width = w;
  out.height = h;
  const ctx = out.getContext('2d');
  ctx.drawImage(baseImg, 0, 0, w, h);
  ctx.drawImage(overlay, 0, 0, w, h);
  return out.toDataURL('image/png');
}
function downloadFinal(){
  if(currentFinalUrl) window.open(currentFinalUrl, '_blank');
}

function regenerate(){
  if(!projectId) return;
  generateVisualization();
}
function downloadProjectZip(){
  if(!projectId) return;
  window.open(`/api/projects/${projectId}/download.zip`, '_blank');
}
function renderArtifacts(files){
  const latest = files.latest || [];
  const items = [
    ['04_prompt_for_chatgpt.txt', 'Промпт для AI (русский)'],
    ['05_prompt_for_gemini_nano_banana.txt', 'Промпт Gemini'],
    ['07_ies_summary.txt', 'IES-сводка'],
    ['08_equipment_draft.md', 'Ведомость'],
    ['04_prompt_for_chatgpt.txt', 'Промпт ChatGPT'],
    ['02_light_plan_reference.png', 'Карта света'],
    ['01_source_building.png', 'Исходник'],
  ];
  const links = items
    .filter(([name]) => latest.some(f => f.name === name))
    .map(([name, label]) => {
      const file = latest.find(f => f.name === name);
      const url = `/api/projects/${projectId}/file/latest/${file.relative_path}`;
      return `<a href="${url}" target="_blank" rel="noopener">${label}</a>`;
    });
  document.getElementById('artifactsHint').style.display = links.length ? 'none' : 'block';
  document.getElementById('artifactsLinks').innerHTML = links.join('');
  document.getElementById('downloadZipBtn').style.display = projectId ? 'inline-block' : 'none';
}
async function refreshLibrary(){
  const data = await api('/api/library');
  document.getElementById('sourceLibrary').innerHTML = (data.source||[]).map(f=>libItem('source',f)).join('') || '<div class="muted">Нет сохраненных фото</div>';
  document.getElementById('iesLibrary').innerHTML = (data.ies||[]).map(f=>libItem('ies',f)).join('') || '<div class="muted">Каталог IES пуст</div>';
}

async function adminAddLibraryIes(){
  const pass = document.getElementById('catalogPass').value || '';
  const ies = document.getElementById('catalogIesFile').files[0];
  const photo = document.getElementById('catalogIesPhoto').files[0];
  if(!ies){
    setStatus('Выберите IES-файл');
    return;
  }
  const fd = new FormData();
  fd.append('password', pass);
  fd.append('ies', ies);
  if(photo) fd.append('photo', photo);
  try{
    await api('/api/admin/library/ies', {method:'POST', body:fd});
    setStatus('IES добавлен в каталог' + (photo ? ' (с фото)' : ''));
    document.getElementById('catalogIesFile').value = '';
    document.getElementById('catalogIesPhoto').value = '';
    refreshLibrary();
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }
}

async function adminDeleteLibraryIes(){
  const pass = document.getElementById('catalogPass').value || '';
  const path = (document.getElementById('catalogIesDeletePath').value || '').trim();
  if(!path){
    setStatus('Укажите имя IES-файла для удаления');
    return;
  }
  const fd = new FormData();
  fd.append('password', pass);
  fd.append('relative_path', path);
  try{
    await api('/api/admin/library/ies', {method:'DELETE', body:fd});
    setStatus('Удалено из каталога');
    document.getElementById('catalogIesDeletePath').value = '';
    refreshLibrary();
  }catch(err){
    setStatus('Ошибка: ' + err.message);
  }
}
async function refresh(){
  if(!projectId) return;
  const p = await api(`/api/projects/${projectId}`);
  lastProjectState = p;
  const files = p.files || {};
  const source = (files.input || []).find(f=>f.name==='building.png');
  const style = (files.references || []).find(f=>f.name==='style_reference_target.png');
  const ies = files.ies || [];
  const light = (files.latest || []).find(f=>f.name==='02_light_plan_reference.png');
  const final = (files.output || []).find(f=>f.name==='final_imported_render.png');
  const sourceBox = document.getElementById('sourcePreviewBox');
  if(source){
    sourceBox.innerHTML = `<img src="/api/projects/${projectId}/file/input/${source.relative_path}?t=${Date.now()}">`;
    sourceBox.classList.add('has-image');
  } else {
    sourceBox.innerHTML = 'Фото здания днём · Ctrl+V или перетащите';
    sourceBox.classList.remove('has-image');
  }
  document.getElementById('sourceName').textContent = source ? `Фото: ${source.name}` : 'Файл не выбран';
  const styleBox = document.getElementById('stylePreviewBox');
  if(style){
    styleBox.innerHTML = `<img src="/api/projects/${projectId}/file/references/${style.relative_path}?t=${Date.now()}">`;
    styleBox.classList.add('has-image');
  } else {
    styleBox.innerHTML = 'Текущий эталон · Ctrl+V для своего';
    styleBox.classList.remove('has-image');
  }
  document.getElementById('styleName').textContent = style ? `Эталон: ${style.name}` : 'Эталон не выбран';
  document.getElementById('iesStatusBox').innerHTML = ies.length ? `Загружено IES: ${ies.length}` : 'IES: нет · подставятся при выборе сценария';
  document.getElementById('iesName').textContent = ies.length ? ies.map(f=>f.name).join(', ') : 'Файлы не выбраны';
  renderIesPreview(ies);
  const renderUsedBlock = document.getElementById('renderUsedBlock');
  const renderIesSection = document.getElementById('renderIesSection');
  const renderIesEmpty = document.getElementById('renderIesEmpty');
  if(final){
    renderUsedBlock.classList.remove('hidden');
    const regenBtn = document.getElementById('regenerateBtn');
    if(regenBtn) regenBtn.style.display = 'inline-block';
    const productName = p.render_product_name || p.dealer_product_name || '';
    const scenarioName = p.render_scenario_name || p.dealer_scenario_name || '';
    const legacyRef = p.render_legacy_ref || p.dealer_legacy_ref || '';
    if(scenarioName){
      document.getElementById('renderScenarioInfo').innerHTML = `<strong>Сценарий:</strong> ${esc(scenarioName)}${productName ? ' · ' + esc(productName) : ''}`;
      document.getElementById('renderScenarioInfo').style.display = 'block';
    } else if(legacyRef){
      document.getElementById('renderScenarioInfo').innerHTML = `<strong>Шаблон:</strong> ${esc(legacyRef)}`;
      document.getElementById('renderScenarioInfo').style.display = 'block';
    } else {
      document.getElementById('renderScenarioInfo').style.display = 'none';
    }
    const iesUsed = p.render_ies_files || [];
    if(iesUsed.length){
      renderIesSection.classList.remove('hidden');
      renderIesEmpty.classList.add('hidden');
      document.getElementById('iesUsedList').innerHTML = renderUsedIesCards(p, ies);
    } else {
      renderIesSection.classList.add('hidden');
      renderIesEmpty.classList.remove('hidden');
      document.getElementById('iesUsedList').innerHTML = '';
    }
  } else {
    renderUsedBlock.classList.add('hidden');
    const regenBtn = document.getElementById('regenerateBtn');
    if(regenBtn) regenBtn.style.display = 'none';
    renderIesSection.classList.add('hidden');
    renderIesEmpty.classList.add('hidden');
    document.getElementById('renderScenarioInfo').innerHTML = '';
    document.getElementById('iesUsedList').innerHTML = '';
  }
  updateWorkflowFromProject(p);
  checkGuidedTourAdvance(p);
  if(p.dealer_scenario_id) selectedDealerScenarioId = p.dealer_scenario_id;
  if(p.dealer_scenario_name){
    document.getElementById('dealerScenarioStatus').textContent =
      `Выбран: ${p.dealer_scenario_name}${p.dealer_product_name ? ' · ' + p.dealer_product_name : ''}`;
  }
  document.getElementById('lightImg').src = light ? `/api/projects/${projectId}/file/latest/${light.relative_path}?t=${Date.now()}` : '';
  currentFinalUrl = final ? `/api/projects/${projectId}/file/output/${final.relative_path}?t=${Date.now()}` : '';
  if(!historyPreviewUrl){
    document.getElementById('finalImg').src = currentFinalUrl;
  }
  renderRenderHistory(p.render_history || []);
  loadEditMarkupImage(final ? currentFinalUrl : '');
  document.getElementById('statusText').textContent = final ? 'Финальный рендер готов' : 'Результат появится здесь после генерации';
  if(final) document.getElementById('resultZone').classList.remove('empty');
  hideContactCta();
  renderArtifacts(files);
  refreshPipelineLog(false);
  refreshLibrary();
  if(p.prompt !== undefined) document.getElementById('prompt').value = p.prompt || '';
  if(p.facade_mode) document.getElementById('facadeMode').value = p.facade_mode;
  if(p.routerai_model) setRouteraiModel(p.routerai_model);
  updateGenerateControls(p);
}
setupEditMarkup();
setEditTool('brush');
setupImagePasteZones();
loadDealerTemplates();
loadRouterModels().then(() => {
  if(lastProjectState && lastProjectState.routerai_model){
    setRouteraiModel(lastProjectState.routerai_model);
  }
  updateGenerateControls(lastProjectState);
});
refreshLibrary();
refreshRenderLimit();
const dealerProject = new URLSearchParams(location.search).get('project');
if(dealerProject) openProject(dealerProject);
else initWelcomeFromLanding();

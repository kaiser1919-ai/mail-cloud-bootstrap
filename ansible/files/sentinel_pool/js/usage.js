(() => {
 'use strict';
 function start() {
  if (window.__sentinelSharedPoolLoaded) return;
  window.__sentinelSharedPoolLoaded=true;
  const box=document.createElement('aside');box.id='sentinel-shared-pool';box.setAttribute('aria-label','Общий диск облака и почты');
  const title=document.createElement('strong');title.textContent='Общий диск · файлы и почта';
  const text=document.createElement('span');text.textContent='Получаем ёмкость…';
  const bar=document.createElement('progress');bar.max=100;bar.setAttribute('aria-label','Занятая часть общего диска');
  box.append(title,text,bar);box.hidden=true;
  let slot=null,host=null,pinned=null,scheduled=false;
  function release() {
   if(host)host.classList.remove('sentinel-pool-host');
   if(pinned)pinned.classList.remove('sentinel-pool-after');
   if(slot)slot.remove();slot=null;host=null;pinned=null;box.hidden=true;
  }
  function place() {
   scheduled=false;
   const nav=document.querySelector('.app-navigation .app-navigation__content');
   if(!nav){release();return;}
   if(host!==nav){release();host=nav;}
   if(!host.classList.contains('sentinel-pool-host'))host.classList.add('sentinel-pool-host');
   const files=host.closest('.files-navigation');
   const trash=files?.querySelector('[data-cy-files-navigation-item="trashbin"]');
   const list=trash?.closest('ul.app-navigation-list');
   const filesSlot=Boolean(list&&host.contains(list)&&trash.parentElement===list);
   const kind=filesSlot?'LI':'DIV';
   if(!slot||slot.tagName!==kind){
    if(slot)slot.remove();slot=document.createElement(kind);slot.className='sentinel-pool-slot';slot.append(box);
   }
   if(filesSlot){
    if(pinned!==trash){if(pinned)pinned.classList.remove('sentinel-pool-after');pinned=trash;}
    if(!trash.classList.contains('sentinel-pool-after'))trash.classList.add('sentinel-pool-after');
    if(slot.parentElement!==list||slot.nextElementSibling!==trash)list.insertBefore(slot,trash);
    if(!slot.classList.contains('sentinel-pool-slot-files'))slot.classList.add('sentinel-pool-slot-files');
   }else{
    if(pinned)pinned.classList.remove('sentinel-pool-after');pinned=null;
    if(slot.classList.contains('sentinel-pool-slot-files'))slot.classList.remove('sentinel-pool-slot-files');
    const children=Array.from(host.children).filter(e=>e!==slot);
    const body=children.find(e=>e.classList.contains('app-navigation__body'));
    const mainList=children.find(e=>e.classList.contains('app-navigation__list'));
    const anchor=mainList||body;
    // Unknown navigation layout: never guess an overlay position.
    if(!anchor){slot.remove();box.hidden=true;return;}
    const next=anchor.nextElementSibling===slot?slot.nextElementSibling:anchor.nextElementSibling;
    if(slot.parentElement!==host||anchor.nextElementSibling!==slot)host.insertBefore(slot,next);
   }
   const wrap=host.closest('.app-navigation');
   const closed=host.getAttribute('aria-hidden')==='true'||host.hasAttribute('inert')||
    wrap?.classList.contains('app-navigation--closed')||wrap?.classList.contains('app-navigation--close');
   const wasHidden=box.hidden;
   if(box.hidden!==Boolean(closed))box.hidden=Boolean(closed);
   box.dataset.layout=filesSlot?'files-before-trash':'navigation-before-footer';
   if(wasHidden&&!box.hidden)refresh();
  }
  function schedule(){if(!scheduled){scheduled=true;requestAnimationFrame(place);}}
  const observer=new MutationObserver(schedule);
  observer.observe(document.body,{childList:true,subtree:true,attributes:true,attributeFilter:['class','aria-hidden','inert']});
  window.addEventListener('resize',schedule);
  const fmt=n=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(n/1073741824)+' ГиБ';
  let active=false;
  async function refresh() {
   if (active || document.hidden || box.hidden) return;
   active=true;const abort=new AbortController();const timer=setTimeout(()=>abort.abort(),6000);
   try {
    const response=await fetch(OC.generateUrl('/apps/sentinel_pool/usage'),{credentials:'same-origin',cache:'no-store',signal:abort.signal});
    if (!response.ok) throw new Error('Unavailable');
    const row=await response.json();
    if (row.status!=='ok' || !['total_bytes','used_bytes','available_bytes','reserved_bytes'].every(k=>Number.isSafeInteger(row[k])&&row[k]>=0) || row.total_bytes<=0 || row.used_bytes+row.available_bytes+row.reserved_bytes!==row.total_bytes) throw new Error('Invalid');
    text.textContent=`Всего ${fmt(row.total_bytes)} · занято ${fmt(row.used_bytes)} · доступно ${fmt(row.available_bytes)}`;
    box.title=`Общий пул всех пользователей. Резерв файловой системы: ${fmt(row.reserved_bytes)}. Измерено: ${new Date(row.measured_at*1000).toLocaleTimeString('ru-RU')}. Задержка обновления — до 70 секунд. Это не личная квота.`;
    bar.value=100*(row.used_bytes+row.reserved_bytes)/row.total_bytes;bar.hidden=false;
    box.classList.toggle('sentinel-pool-low',row.available_bytes/row.total_bytes<0.1);box.classList.remove('sentinel-pool-unavailable');
   } catch (_) {
    text.textContent='Данные о ёмкости временно недоступны';bar.hidden=true;box.classList.add('sentinel-pool-unavailable');box.classList.remove('sentinel-pool-low');box.title='Показания не подтверждены. Не используем устаревшие данные или ёмкость системного диска.';
   } finally {clearTimeout(timer);active=false;}
  }
  place();setInterval(refresh,30000);document.addEventListener('visibilitychange',()=>{if(!document.hidden){schedule();refresh();}});
 }
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',start,{once:true});else start();
})();

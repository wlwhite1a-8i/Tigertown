'use strict';
// Plain JavaScript frontend. MySQL is accessed only through the server API.
const $ = (s, root=document) => root.querySelector(s);
const $$ = (s, root=document) => [...root.querySelectorAll(s)];
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeURL = value => { try { const u=new URL(value); return ['https:','http:'].includes(u.protocol) ? escapeHTML(u.href) : ''; } catch { return ''; } };
const label = value => String(value || '').replaceAll('_',' ').replace(/\b\w/g, c=>c.toUpperCase());
const friendlyNote = value => String(value||'').replaceAll('place_identity_candidates','the possible matches section').replaceAll('place_branches','the local branches section').replaceAll('JSON-LD location','official website location data').replaceAll('JSON-LD branch record','official branch location record').replaceAll('map coordinates are location coordinates, not a viewport. ','').replaceAll('Survey parent does not identify this particular branch.','The survey does not identify this particular branch.');
const statusLabel = value => ({verified:'Identity verified',needs_clarification:'Match to confirm',unverified:'Not yet verified'}[value] || 'Not yet verified');
let saved = new Set();
try { saved = new Set(JSON.parse(localStorage.getItem('tigertown-saved') || '[]').filter(Number.isInteger)); } catch { /* Storage may be unavailable. */ }
const state = { data:null, config:{mode:'preview'}, category:'', limit:9, csrf:'', admin:false, active:'explore', busy:false, etag:'' };
let toastTimer;
function toast(message) { $('#toast').textContent=message; $('#toast').hidden=false; clearTimeout(toastTimer); toastTimer=setTimeout(()=>$('#toast').hidden=true,3200); }
const heart = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" aria-hidden="true"><path d="M20.8 4.6a5.4 5.4 0 0 0-7.6 0L12 5.8l-1.2-1.2a5.4 5.4 0 0 0-7.6 7.6L12 22l8.8-9.8a5.4 5.4 0 0 0 0-7.6Z"/></svg>';
function icon(type) {
  const paths = type==='museum' ? '<path d="m3 9 9-6 9 6H3Zm2 3v7m5-7v7m4-7v7m5-7v7M3 22h18"/>' : type==='library' ? '<path d="M12 5c-3-3-7-3-10-2v16c4-1 7 0 10 2 3-2 6-3 10-2V3c-3-1-7-1-10 2Zm0 0v16M5 7l4 1M5 11l4 1m6-4 4-1m-4 5 4-1"/>' : ['outdoor_area','neighborhood'].includes(type) ? '<path d="m12 2-7 9h4l-6 8h8v4m2 0v-4h8l-6-8h4L12 2Z"/>' : type==='shopping_area' ? '<path d="M4 7h16l2 15H2L4 7Zm4 0V5a4 4 0 0 1 8 0v2"/>' : type==='sports_venue' ? '<circle cx="12" cy="12" r="10"/><path d="m7 3 5 7 8-3M3 7l7 5-3 8m10-17-3 7 7 4m-18 3 7-3 4 7"/>' : '<circle cx="13" cy="12" r="7"/><circle cx="13" cy="12" r="4"/><path d="M2 2v7m3-7v7M2 6h3M3.5 9v13M23 2v20"/>';
  return `<svg class="big-icon" viewBox="0 0 26 26" fill="none" stroke="currentColor" stroke-width=".9" stroke-linejoin="round" aria-hidden="true">${paths}</svg>`;
}
function price(p) {
  const lo=p.price_min_usd, hi=p.price_max_usd;
  if(lo==null && hi==null) return 'Price not verified';
  const fmt=x=>Number(x).toLocaleString('en-US',{style:'currency',currency:'USD',minimumFractionDigits:Number(x)%1?2:0,maximumFractionDigits:2});
  if(lo!=null && hi!=null) return Number(lo)===Number(hi)?fmt(lo):`${fmt(lo)}–${fmt(hi)}`;
  return lo!=null ? `From ${fmt(lo)}` : `Up to ${fmt(hi)}`;
}
function placeCity(p) { return p.city || (p.branches?.length ? [...new Set(p.branches.map(b=>b.city))].join(' · ') : (p.reported_area || 'Jackson area · exact spot to confirm')); }
function card(p) {
  const checked=p.verification_status==='verified';
  return `<article class="place-card"><button type="button" class="card-art tone-${p.place_id%4}" data-detail="${p.place_id}" aria-label="Explore ${escapeHTML(p.display_name)}">${icon(p.place_kind)}<svg class="card-spirit-paw" viewBox="0 0 100 92" aria-hidden="true"><use href="#tt-paw"/></svg><span class="card-location">${escapeHTML(placeCity(p).toUpperCase())}</span></button><button class="save-button" data-save="${p.place_id}" aria-pressed="${saved.has(p.place_id)}" aria-label="${saved.has(p.place_id)?'Unsave':'Save'} ${escapeHTML(p.display_name)}">${heart}</button><div class="card-body"><div class="card-top"><span class="badge ${checked?'verified':p.verification_status==='needs_clarification'?'needs_clarification':''}">${checked?'✓ ':''}${statusLabel(p.verification_status)}</span><span class="card-type">${escapeHTML((['neighborhood','outdoor_area','shopping_area'].includes(p.place_kind)?label(p.place_kind):p.categories?.[0]?.category_name) || label(p.place_kind))}</span></div><h3 class="card-title">${escapeHTML(p.display_name)}</h3><p class="card-description">${escapeHTML(p.menu_services || (p.branches?.length ? `${p.branches.length} documented local branch${p.branches.length===1?'':'es'}. Choose a location to see its details.` : p.candidates?.length ? `${p.candidates.length} possible match${p.candidates.length===1?'':'es'}. Open this place to review the researched options.` : 'This survey suggestion did not identify a specific venue. Its exact location still needs confirmation.'))}</p><div class="card-bottom"><div class="price-sample">${price(p)}<small>${p.price_basis?'Published sample · see basis':p.branches?.length?`${p.branches.length} local branch${p.branches.length===1?'':'es'}`:'Check the venue for current prices'}</small></div><button class="detail-button" data-detail="${p.place_id}">View place <span aria-hidden="true">↗</span></button></div></div></article>`;
}
function filters() { return {q:$('#search').value.trim().toLowerCase(),city:$('#city-filter').value,status:$('#status-filter').value,sort:$('#sort-filter').value}; }
function filtered() {
  const f=filters();
  return state.data.places.filter(p=>{
    const haystack=[p.display_name,p.canonical_name,p.menu_services,p.reported_area,p.city,...(p.aliases||[]),...(p.branches||[]).flatMap(b=>[b.branch_name,b.street_address,b.city])].join(' ').toLowerCase();
    return (!f.q || haystack.includes(f.q)) && (!state.category || (p.categories||[]).some(c=>String(c.category_id)===state.category)) && (!f.city || p.city===f.city || (p.branches||[]).some(b=>b.city===f.city)) && (!f.status || p.verification_status===f.status);
  }).sort((a,b)=> f.sort==='popular' ? (b.survey_votes-a.survey_votes || a.display_name.localeCompare(b.display_name)) : f.sort==='city' ? placeCity(a).localeCompare(placeCity(b)) || a.display_name.localeCompare(b.display_name) : a.display_name.localeCompare(b.display_name));
}
function drawResults(reset=false) {
  if(!state.data)return;
  if(reset)state.limit=9;
  const items=filtered();
  $('#result-count').textContent=`${items.length} ${items.length===1?'place':'places'} to explore${state.category?' · '+(state.data.categories.find(c=>String(c.category_id)===state.category)?.category_name||''):''}`;
  $('#place-grid').innerHTML=items.length?items.slice(0,state.limit).map(card).join(''):'<div class="empty"><h3>A different direction?</h3><p>No places match those filters. Try another city or clear the search.</p><button class="button outline" data-reset>Clear filters</button></div>';
  $('#load-more').hidden=items.length<=state.limit;
  $$('#category-tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.category===state.category)));
  const f=filters(), params=new URLSearchParams();
  if(f.q)params.set('q',$('#search').value.trim());if(f.city)params.set('city',f.city);if(f.status)params.set('status',f.status);if(state.category)params.set('category',state.category);if(f.sort!=='name')params.set('sort',f.sort);
  history.replaceState(null,'',location.pathname+(params.size?'?'+params:'')+(location.hash||'#explore'));
  enhancePlaceCards();
}
function resetFilters(){ $('#search').value='';$('#city-filter').value='';$('#status-filter').value='';$('#sort-filter').value='name';state.category='';drawResults(true); }
function drawSaved() { if(!state.data)return; const items=state.data.places.filter(p=>saved.has(p.place_id));$('#saved-count').textContent=String(items.length);$('#saved-grid').innerHTML=items.length?items.map(card).join(''):'<div class="empty"><h3>Your list starts here.</h3><p>Tap the heart on any place to keep it for later.</p><a class="button primary" href="#explore">Explore places ↗</a></div>'; enhancePlaceCards(); }
function toggleSaved(id) { if(saved.has(id))saved.delete(id);else saved.add(id); try{localStorage.setItem('tigertown-saved',JSON.stringify([...saved]));}catch{toast('Saved for this visit. Browser storage is unavailable.');}drawSaved();drawResults();if(saved.has(id)&&!motionPaused)$$(`[data-save="${id}"]`).forEach(b=>b.classList.add('just-saved')); }
function sourceLink(url,text='View source ↗'){const u=safeURL(url);return u?`<a class="source-link" href="${u}" target="_blank" rel="noopener noreferrer">${escapeHTML(text)}</a>`:'';}
function address(p){return [p.street_address,[p.city,p.state_code,p.postal_code].filter(Boolean).join(', ')].filter(Boolean).join('\n');}
function locationLink(p) {if(p.latitude!=null&&p.longitude!=null)return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(`${p.latitude},${p.longitude}`);if(p.street_address)return 'https://www.google.com/maps/search/?api=1&query='+encodeURIComponent(address(p));return null;}
function detailItem(title,value,extra=''){return `<div class="detail-item"><dt>${escapeHTML(title)}</dt><dd>${escapeHTML(value||'Not verified yet.')}${extra}</dd></div>`;}
function venueSubcard(b,candidate=false){return `<article class="subcard ${candidate?'candidate':''}"><h4>${escapeHTML(b.branch_name||b.candidate_name)}</h4><p>${escapeHTML(address(b))}</p>${b.hours_summary?`<p>${escapeHTML(b.hours_summary)}</p>`:''}${b.menu_services?`<p>${escapeHTML(b.menu_services)}</p>`:''}${b.phone?`<p>Phone: ${escapeHTML(b.phone)}</p>`:''}${b.price_basis?`<p><strong>${price(b)}</strong> · ${escapeHTML(b.price_basis)}</p>`:''}<p class="subtle">${escapeHTML(friendlyNote(b.notes||''))}</p>${sourceLink(b.source_url)} ${b.price_source_url&&b.price_source_url!==b.source_url?sourceLink(b.price_source_url,'Price source ↗'):''}</article>`;}
function showPlace(id) {
  const p=state.data?.places.find(p=>p.place_id===id);if(!p)return;
  const map=locationLink(p), homepage=safeURL(p.website_url), checked=String(p.verified_at||'').slice(0,10), reviewCount=Number(p.review_count||0);
  $('#place-detail').innerHTML=`<div class="detail-head"><span class="badge ${p.verification_status==='verified'?'verified':'needs_clarification'}">${statusLabel(p.verification_status)}</span><h2 id="detail-title">${escapeHTML(p.display_name)}</h2><p>${escapeHTML(p.canonical_name&&p.canonical_name!==p.display_name?p.canonical_name:placeCity(p))}</p><div class="detail-actions">${homepage?`<a class="button primary" href="${homepage}" target="_blank" rel="noopener noreferrer">Visit website ↗</a>`:''}${map?`<a class="button outline" href="${escapeHTML(map)}" target="_blank" rel="noopener noreferrer">Directions ↗</a>`:''}<button class="button outline" data-save="${id}">${saved.has(id)?'Saved ✓':'Save this place ♡'}</button></div></div><div class="detail-body"><dl class="detail-grid">${detailItem('Location',p.street_address?address(p):p.place_kind==='neighborhood'||p.place_kind==='outdoor_area'?'Area-level destination; choose a specific venue or access point.':p.branches?.length?'Choose a documented branch below.':'Exact address needs confirmation.')}${detailItem('Hours',p.hours_summary)}${detailItem('Menu & things to do',p.menu_services)}${detailItem('Price sample',price(p),p.price_basis?`<small>${escapeHTML(p.price_basis)}</small>`:'<small>Unknown does not mean free. Branch-specific prices may appear below.</small>')}${detailItem('Student offers',p.student_discount_summary||'No current student-specific offer has been verified. Ask the venue; this does not mean no offer exists.')}${detailItem('Student survey mentions',`${p.survey_votes||0} respondent${p.survey_votes===1?'':'s'} named this as a favorite.`, '<small>Survey mentions measure interest, not star ratings.</small>')}</dl>${p.branches?.length?`<h3>Choose a local branch.</h3><p class="subtle">The survey name does not identify one particular branch. These are documented local options.</p><br>${p.branches.map(b=>venueSubcard(b)).join('')}`:''}${p.candidates?.length?`<h3>Possible matches.</h3><p class="subtle">These venues exist, but their match to the survey response is unconfirmed.</p><br>${p.candidates.map(c=>venueSubcard(c,true)).join('')}`:''}<div class="research-note"><strong>RESEARCH CONTEXT${checked?' · '+escapeHTML(checked):''}</strong><p>${escapeHTML(friendlyNote(p.research_notes||p.identity_notes||'This place has not been independently verified.'))}</p>${sourceLink(p.verification_source_url||p.primary_source_url)}</div>${p.field_notes?.length?`<details><summary>Field verification notes (${p.field_notes.length})</summary><p class="subtle">Research snapshot; later manual updates can differ.</p><div class="table-scroll"><table><thead><tr><th>Detail</th><th>Research status & context</th></tr></thead><tbody>${p.field_notes.map(f=>`<tr><td>${escapeHTML(label(f.field_name))}</td><td>${escapeHTML(label(f.research_status))}<p class="subtle">${escapeHTML(f.notes)}</p>${sourceLink(f.source_url)}</td></tr>`).join('')}</tbody></table></div></details>`:''}${reviewCount?`<h3>Recorded reviews</h3><p class="subtle">${reviewCount} review${reviewCount===1?'':'s'} · average ${escapeHTML(p.average_rating)} / 5. Review provenance is kept in the database.</p>`:''}</div>`;
  $('#place-dialog').showModal();
}
async function api(path,options={}) {
  const response=await fetch(path,{credentials:'same-origin',...options,headers:{'Content-Type':'application/json','X-CSRF-Token':state.csrf,...options.headers}});
  let data;try{data=await response.json();}catch{throw new Error('The server returned an unexpected response.');}
  if(!response.ok)throw new Error(data.error||'The request could not be completed.');return data;
}
function catalogNotice(){
  if(state.config.mode==='preview')return 'Research preview. Search, browse, and save places here. Database editing becomes available when this website is connected to your MySQL server.';
  return 'Live MySQL catalog · updates are controlled by the administrator. Check the source before visiting; hours and prices can change.';
}
async function loadData(){
  const response=await fetch(state.config.mode==='mysql'?'/api/catalog':'/catalog.json',{cache:'no-store',headers:state.config.mode==='mysql'&&state.etag?{'If-None-Match':state.etag}:{}});
  if(response.status===304){$('#catalog-notice').textContent=catalogNotice();return false;}
  const data=await response.json();if(!response.ok)throw new Error(data.error||'The catalog could not be loaded.');state.data=data;state.etag=response.headers.get('ETag')||'';
  $('#stats').innerHTML=`<div class="stat"><strong>${data.places.length}</strong><span class="stat-label">places<br>to explore</span></div><div class="stat"><strong>${data.places.reduce((n,p)=>n+(p.branches||[]).length,0)}</strong><span class="stat-label">documented<br>local branches</span></div><div class="stat"><strong>${data.categories.length}</strong><span class="stat-label">ways to<br>find your spot</span></div><p class="stat-end"><span class="dot"></span>${state.config.mode==='mysql'?'Live MySQL catalog':'Research catalog · Oct 25, 2026'}</p>`;
  const cities=[...new Set(data.places.flatMap(p=>[p.city,...(p.branches||[]).map(b=>b.city)]).filter(Boolean))].sort();
  const oldCity=$('#city-filter').value;if(oldCity&&!cities.includes(oldCity))cities.push(oldCity);$('#city-filter').innerHTML='<option value="">All cities & areas</option>'+cities.map(c=>`<option value="${escapeHTML(c)}">${escapeHTML(c)}</option>`).join('');$('#city-filter').value=oldCity;
  const tabLabels={'Restaurants':'Food & drink','Shopping':'Shopping','Parks/Outdoor Activities':'Outdoors','Study Spots':'Study spots','Nightlife':'Nightlife','Entertainment':'Entertainment','Museums and Culture':'Arts & culture','Sports':'Sports'};
  $('#category-tabs').innerHTML='<button type="button" class="category-tab" data-category="" aria-pressed="true">All places</button>'+data.categories.map((c,i)=>`<button type="button" class="category-tab" data-category="${c.category_id}" aria-pressed="false"><span>${String(i+1).padStart(2,'0')}</span>${escapeHTML(tabLabels[c.category_name]||c.category_name)}</button>`).join('');
  $('#catalog-notice').textContent=catalogNotice();
  drawResults();drawSaved();return true;
}
async function refreshCatalog(){
  if(state.config.mode!=='mysql'||!state.admin||state.busy)return;
  state.busy=true;
  const previous=new Set((state.data?.places||[]).map(p=>p.place_id));
  try{const changed=await loadData();if(changed&&state.active==='admin')drawAdmin();const added=state.data.places.filter(p=>!previous.has(p.place_id));toast(added.length?`Catalog refreshed · ${added.length} new place${added.length===1?'':'s'}.`:'Catalog is up to date.');}
  catch(error){$('#catalog-notice').textContent='Unable to refresh the catalog. The displayed list may be out of date. '+error.message;toast('Refresh failed. Check the database connection.');}
  finally{state.busy=false;}
}
function route(){
  const name=location.hash.slice(1);state.active=['saved','about','admin'].includes(name)?name:'explore';
  $$('.page').forEach(p=>p.hidden=p.id!==state.active+'-page');$$('[data-nav]').forEach(a=>a.classList.toggle('active',a.dataset.nav===state.active));
  if(state.active==='admin')drawAdmin();if(state.active==='saved')drawSaved();
  if(name==='results')setTimeout(()=>$('#results').scrollIntoView(),0);else if(!name||name!=='explore')window.scrollTo(0,0);
}
function drawAdmin(){
  const target=$('#admin-content');$('#logout').hidden=!state.admin;
  if(state.config.mode!=='mysql'){
    target.innerHTML='<div class="preview-panel"><h2>The website is ready for your database.</h2><p>You’re viewing the researched catalog. To add and update real records, run the included website server with your MySQL connection. The HTML frontend stays the same.</p><a class="button primary" href="/downloads/TigerTown_Website_MySQL.zip" download>Download the VS Code project ↗</a><details><summary>Connect it on your computer</summary><ol><li>Extract the folder and open it in Visual Studio Code.</li><li>Follow <code>START_HERE.md</code> to install the Python server dependencies.</li><li>Run <code>python server/setup.py</code> to enter your MySQL settings privately.</li><li>Run <code>python server/server.py</code>, open the local website, and sign in here.</li></ol><p>MySQL passwords belong on the server. Live Server alone displays the frontend but does not connect to MySQL.</p></details></div>';return;
  }
  if(!state.admin){target.innerHTML='<form id="login-form" class="login-card"><h2>Administrator sign-in</h2><p class="subtle">Use the administrator password you set during website setup.</p><br><label class="form-field">Password<input type="password" name="password" required autocomplete="current-password" maxlength="200"></label><p class="error-message" id="login-error" role="alert"></p><button class="button primary" type="submit">Sign in ↗</button></form>';return;}
  const places=state.data?.places||[];
  target.innerHTML=`<div class="admin-toolbar"><p>${places.length} places · changes are saved to MySQL.</p><div class="admin-controls"><button class="button outline" data-refresh>Refresh catalog ↻</button><button class="button primary" data-new>Add a place +</button></div></div><p class="subtle">Original survey responses and historical research notes are preserved. Updating a place does not rewrite the research snapshot.</p><div class="table-scroll"><table><thead><tr><th>Place</th><th>City / branches</th><th>Identity</th><th>Action</th></tr></thead><tbody>${places.map(p=>`<tr><td><strong>${escapeHTML(p.display_name)}</strong></td><td>${escapeHTML(placeCity(p))}</td><td><span class="badge ${p.verification_status==='verified'?'verified':'needs_clarification'}">${statusLabel(p.verification_status)}</span></td><td><button class="text-button" data-edit="${p.place_id}">Edit place</button></td></tr>`).join('')}</tbody></table></div>`;
}
const editable=[['display_name','Place name','text',true],['place_kind','Place type','kind',true],['city','City'],['street_address','Street address'],['state_code','State (2 letters)'],['postal_code','ZIP code'],['latitude','Latitude','number'],['longitude','Longitude','number'],['website_url','Official website','url'],['menu_services','Menu / things to do','textarea'],['hours_summary','Hours','textarea'],['student_discount_summary','Student offers','textarea'],['price_min_usd','Sample minimum ($)','number'],['price_max_usd','Sample maximum ($)','number'],['price_basis','What does this price cover?'],['verification_status','Identity status','status'],['verification_source_url','Verification source','url']];
function showEditor(id=null){
  const p=id?state.data.places.find(p=>p.place_id===id):{};if(!p)return;
  const kinds=['business','neighborhood','shopping_area','outdoor_area','library','sports_venue','museum','unspecified_place'];
  const input=(key,title,type='text',required=false)=>{const value=p[key]??(key==='state_code'?'MS':key==='verification_status'?'unverified':'');const opts=type==='kind'?kinds:type==='status'?['unverified','needs_clarification','verified']:null;return `<label class="form-field ${type==='textarea'||['display_name','price_basis','verification_source_url','website_url'].includes(key)?'full':''}">${escapeHTML(title)}${required?' *':''}${opts?`<select name="${key}">${opts.map(o=>`<option value="${o}" ${o===value?'selected':''}>${escapeHTML(label(o))}</option>`).join('')}</select>`:type==='textarea'?`<textarea name="${key}" maxlength="4000">${escapeHTML(value)}</textarea>`:`<input name="${key}" value="${escapeHTML(value)}" type="${type}" ${type==='number'?'step="any"':''} ${required?'required':''} ${['state_code','postal_code'].includes(key)?`maxlength="${key==='state_code'?2:16}"`:'maxlength="255"'}>`}</label>`;};
  $('#edit-content').innerHTML=`<form id="edit-form" class="edit-wrap" data-id="${id||''}"><h2 id="edit-title">${id?'Update this place.':'Add a local place.'}</h2><p class="subtle">Leave unknown details blank. Verified identities require a source. Price samples need a clear basis.</p><input type="hidden" name="revision" value="${escapeHTML(p.revision||'')}"><div class="edit-grid">${editable.map(f=>input(...f)).join('')}<h3 class="form-section">Categories</h3><div class="full check-grid">${state.data.categories.map(c=>`<label><input type="checkbox" name="categories" value="${c.category_id}" ${(p.categories||[]).some(x=>x.category_id===c.category_id)?'checked':''}>${escapeHTML(c.category_name)}</label>`).join('')}</div>${!id?'<label class="form-field full">Identity / context notes<textarea name="identity_notes" maxlength="4000" placeholder="How was this place identified?"></textarea></label>':''}</div><p class="error-message" id="edit-error" role="alert"></p><button class="button primary" type="submit">Save to database ↗</button></form>`;$('#edit-dialog').showModal();
}
document.addEventListener('click',e=>{
  const cityFocus=e.target.closest('[data-city-focus]');if(cityFocus){resetFilters();$('#city-filter').value=cityFocus.dataset.cityFocus;drawResults(true);location.hash='results';$('#results').scrollIntoView({behavior:motionPaused?'auto':'smooth'});return;}
  if(e.target.closest('[data-spirit]')){const field=$('.home-field');field.classList.remove('tiger-cheer');requestAnimationFrame(()=>field.classList.add('tiger-cheer'));toast('GO TIGERS! Carry that Tiger pride into the city.');return;}
  const launch=e.target.closest('[data-picker]');if(launch){openPicker(launch.dataset.picker||'');return;}
  const choice=e.target.closest('[data-pick-vibe]');if(choice){picker.category=choice.dataset.pickVibe;drawVibeChoices();$('#picker-result').innerHTML='';return;}
  const match=e.target.closest('[data-open-pick]');if(match){$('#picker-dialog').close();showPlace(Number(match.dataset.openPick));return;}
  if(e.target.closest('[data-roll-again]')){pickPlace();return;}
  const save=e.target.closest('[data-save]');if(save){toggleSaved(Number(save.dataset.save));if($('#place-dialog').open){const id=Number(save.dataset.save);$('#place-dialog').close();showPlace(id);}return;}
  const detail=e.target.closest('[data-detail]');if(detail){showPlace(Number(detail.dataset.detail));return;}
  const cat=e.target.closest('[data-category]');if(cat){state.category=cat.dataset.category;drawResults(true);return;}
  const close=e.target.closest('[data-close]');if(close){close.closest('dialog').close();return;}
  if(e.target.closest('[data-reset]'))resetFilters();
  if(e.target.closest('[data-edit]'))showEditor(Number(e.target.closest('[data-edit]').dataset.edit));
  if(e.target.closest('[data-new]'))showEditor();
  if(e.target.closest('[data-refresh]'))refreshCatalog();
});
document.addEventListener('submit',async e=>{
  if(e.target.id==='search-form'){e.preventDefault();drawResults(true);return;}
  if(!['login-form','edit-form'].includes(e.target.id))return;
  e.preventDefault();const form=e.target;const button=$('button[type=submit]',form);const error=$(form.id==='login-form'?'#login-error':'#edit-error');error.textContent='';button.disabled=true;state.busy=true;
  try{
    if(form.id==='login-form'){const result=await api('/api/login',{method:'POST',body:JSON.stringify({password:new FormData(form).get('password')})});state.csrf=result.csrf;state.admin=true;state.etag='';await loadData();drawAdmin();toast('Signed in. You can manage the catalog.');}
    else{const fd=new FormData(form),body=Object.fromEntries(fd);body.categories=fd.getAll('categories').map(Number);const id=form.dataset.id;await api(id?'/api/places/'+id:'/api/places',{method:id?'PUT':'POST',body:JSON.stringify(body)});$('#edit-dialog').close();state.etag='';await loadData();drawAdmin();toast('Place saved to MySQL.');}
  }catch(err){error.textContent=err.message;}finally{button.disabled=false;state.busy=false;}
});
$('#logout').addEventListener('click',async()=>{try{const result=await api('/api/logout',{method:'POST',body:'{}'});state.admin=false;state.csrf=result.csrf;drawAdmin();}catch(e){toast(e.message);}});
$('#clear-filters').addEventListener('click',resetFilters);
$('#load-more').addEventListener('click',()=>{state.limit+=9;drawResults();});
['#city-filter','#status-filter','#sort-filter'].forEach(s=>$(s).addEventListener('change',()=>drawResults(true)));
let searchTimer;$('#search').addEventListener('input',()=>{clearTimeout(searchTimer);searchTimer=setTimeout(()=>drawResults(true),180);});
window.addEventListener('hashchange',route);
// No polling or background refresh: administrators control catalog updates.
async function init(){
  try{
    const configResponse=await fetch('/site-config.json',{cache:'no-store'});if(!configResponse.ok)throw new Error('Website configuration could not be loaded.');state.config=await configResponse.json();
    if(state.config.mode==='mysql'){const config=await api('/api/session');state.csrf=config.csrf;state.admin=config.admin;}
    const params=new URLSearchParams(location.search);$('#search').value=params.get('q')||'';$('#status-filter').value=params.get('status')||'';$('#sort-filter').value=params.get('sort')||'name';state.category=params.get('category')||'';
    await loadData();if(params.get('city')){$('#city-filter').value=params.get('city');drawResults();}route();
  }catch(err){$('#stats').textContent='Catalog unavailable';$('#result-count').textContent='Unable to load places';$('#catalog-notice').classList.add('error');$('#catalog-notice').textContent=err.message;$('#place-grid').innerHTML='<div class="empty"><h3>We couldn’t load the guide.</h3><p>Check the website server and MySQL connection, then reload this page.</p><button class="button outline" id="retry-load">Try again</button></div>';$('#retry-load').addEventListener('click',()=>location.reload());route();}
}
// Explorer interactions use the loaded catalog only. No background database requests.
const VIBES = [
  {id:'',name:'Surprise me',symbol:'✦'},
  {id:'1',name:'Food run',symbol:'⌁'},
  {id:'4',name:'Study break',symbol:'⌑'},
  {id:'3',name:'Fresh air',symbol:'♧'},
  {id:'7',name:'Culture trip',symbol:'✳'},
  {id:'2',name:'Shopping',symbol:'▱'},
  {id:'8',name:'Game day',symbol:'◎'},
  {id:'6',name:'Hang out',symbol:'✌'}
];
const picker={category:'',lastId:null};
let motionPaused=window.matchMedia('(prefers-reduced-motion: reduce)').matches;
try{motionPaused=motionPaused||localStorage.getItem('tigertown-motion')==='paused';}catch{}
let revealObserver=null;
function enhancePlaceCards(){
  if(!revealObserver)return;
  revealObserver.disconnect();
  $$('.place-card').forEach(card=>{
    if(card.classList.contains('reveal-visible'))return;
    card.classList.add('reveal-pending');revealObserver.observe(card);
  });
}
function drawVibeChoices(){
  $('#picker-vibes').innerHTML=VIBES.map(v=>`<button type="button" class="pick-vibe" data-pick-vibe="${v.id}" aria-pressed="${picker.category===v.id}"><span aria-hidden="true">${v.symbol}</span>${v.name}</button>`).join('');
}
function openPicker(category=''){
  if(!state.data){toast('The guide is still loading. Try again in a moment.');return;}
  picker.category=VIBES.some(v=>v.id===category)?category:'';picker.lastId=null;
  drawVibeChoices();
  const cities=[...new Set(state.data.places.filter(p=>p.verification_status==='verified').map(p=>p.city).filter(Boolean))].sort();
  $('#picker-city').innerHTML='<option value="">Anywhere in the guide</option>'+cities.map(c=>`<option value="${escapeHTML(c)}">${escapeHTML(c)}</option>`).join('');
  $('#picker-city').value=cities.includes($('#city-filter').value)?$('#city-filter').value:'';
  $('#picker-result').innerHTML='';$('#picker-dialog').showModal();
}
function pickPlace(){
  if(!state.data)return;
  const city=$('#picker-city').value;
  const eligible=state.data.places.filter(p=>p.verification_status==='verified'&&(!picker.category||(p.categories||[]).some(c=>String(c.category_id)===picker.category))&&(!city||p.city===city));
  const result=$('#picker-result');
  if(!eligible.length){result.innerHTML='<h3>Still exploring this corner.</h3><p class="match-reason">There isn’t an identified place for that combination in the guide yet. Try another vibe or choose anywhere.</p>';return;}
  const alternatives=eligible.filter(p=>p.place_id!==picker.lastId);
  const pool=alternatives.length?alternatives:eligible;
  const p=pool[Math.floor(Math.random()*pool.length)];picker.lastId=p.place_id;
  const vibe=VIBES.find(v=>v.id===picker.category)?.name;
  const area=['neighborhood','outdoor_area'].includes(p.place_kind);
  result.innerHTML=`<div class="match-confetti" aria-hidden="true"><span></span><span></span><span></span><span></span></div><p class="eyebrow">HERE’S A LITTLE INSPIRATION</p><h3>${escapeHTML(p.display_name)}</h3><p class="match-city">${escapeHTML(p.city||'Jackson area')} · ${escapeHTML(label(p.place_kind))}</p><p class="match-reason">${escapeHTML(p.menu_services||'Explore the venue details to plan your visit.')}</p><div class="match-actions"><button type="button" class="button primary" data-open-pick="${p.place_id}">Explore this spot ↗</button>${eligible.length>1?'<button type="button" class="text-button" data-roll-again>Try another ↻</button>':''}</div><p class="match-foot">${picker.category?escapeHTML(vibe)+' · ':''}${eligible.length} identified ${eligible.length===1?'match':'matches'}${area?' · Area suggestion: choose a specific access point or business.':'. Check hours and details before heading out.'}</p>`;
  if(!motionPaused)result.animate([{opacity:0,transform:'translateY(10px) scale(.97)'},{opacity:1,transform:'none'}],{duration:280,easing:'ease-out'});
}
function updateMotionControl(){
  document.documentElement.classList.toggle('motion-paused',motionPaused);
  $('#motion-toggle').setAttribute('aria-pressed',String(motionPaused));
  $('#motion-toggle').setAttribute('aria-label',motionPaused?'Resume playful animations':'Pause playful animations');
  $('#motion-toggle').innerHTML='<span aria-hidden="true">◌</span> Motion '+(motionPaused?'off':'on');
}
function setupPlayfulInteractions(){
  updateMotionControl();
  if('IntersectionObserver' in window){
    revealObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{
      if(!entry.isIntersecting)return;
      entry.target.classList.remove('reveal-pending');entry.target.classList.add('reveal-visible');revealObserver.unobserve(entry.target);
    }),{threshold:.08});
  }
  $('#motion-toggle').addEventListener('click',()=>{
    if(window.matchMedia('(prefers-reduced-motion: reduce)').matches){motionPaused=true;toast('Animations are reduced by your device settings.');}
    else motionPaused=!motionPaused;
    try{localStorage.setItem('tigertown-motion',motionPaused?'paused':'on');}catch{}
    updateMotionControl();
  });
  $('#picker-go').addEventListener('click',pickPlace);
  $('#picker-city').addEventListener('change',()=>{$('#picker-result').innerHTML='';picker.lastId=null;});
  let scrolling=false;
  window.addEventListener('scroll',()=>{
    if(motionPaused||scrolling||state.active!=='explore')return;
    scrolling=true;requestAnimationFrame(()=>{
      $('.playground').style.setProperty('--parallax',`${Math.min(window.scrollY*.06,24)}px`);scrolling=false;
    });
  },{passive:true});
}
setupPlayfulInteractions();
init();

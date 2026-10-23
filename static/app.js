import {$,el,api,notify,button,money,pct,metric,tag,facts,nav} from './common.js';
let state;
async function load(keep){
 state=await api('/api/state');const select=$('#customer');select.replaceChildren(...state.users.map(u=>{const o=el('option',u.name);o.value=u.id;return o}));if(keep)select.value=keep;
 $('#rating-item').replaceChildren(...state.catalog.map(i=>{const o=el('option',i.name);o.value=i.id;return o}));
 const m=state.evaluation;$('#metrics').replaceChildren(metric('Products in catalog',state.catalog.length,'four product categories'),metric('Test customers',state.users.length,'synthetic starting profiles'),metric('Recorded ratings',state.ratings,'explicit feedback'),metric('Holdout hit rate @5',pct(m.hit_rate_at_5),'fixed 50/50 evaluation'));
 $('#evaluation-metrics').replaceChildren(metric('Hit rate @5',pct(m.hit_rate_at_5),'held-out positive found'),metric('Customers evaluated',m.users_evaluated,'one holdout each'),metric('Interactions held out',m.held_out,'removed before ranking'),metric('Evaluation version',m.version,'persisted locally'));
 $('#evaluation-facts').replaceChildren(facts([['Run at',new Date(m.created).toLocaleString()],['Method',m.method],['Dataset',m.source]]));await recommend();
}
async function recommend(){
 const rows=await api('/api/recommend?user_id='+$('#customer').value+'&weight='+$('#weight').value),list=$('#recommendations');list.replaceChildren();
 $('#rank-note').textContent=rows[0]?.cold_start?'No ratings yet. Showing Bayesian-smoothed catalog popularity.':'Ranked blend. Rated products are excluded.';
 for(const [index,r]of rows.entries()){const card=el('article',undefined,'item');card.append(tag(r.item.category),el('h3',r.item.name),el('p',r.item.description),el('h3',money(r.item.price)),el('div','Rank '+(index+1)+' · blended score '+r.score.toFixed(3),'note'),el('hr',undefined,'rule'),facts([['Content affinity',pct(r.content)],['Neighbor score',pct(r.collaborative)]]),el('p',r.reason,'note'),button('Rate this product',()=>{$('#rating-item').value=r.item.id;$('#rating-value').focus()},'plain'));list.append(card)}
 if(!rows.length)list.append(el('p','This customer has rated every product. Add a new test customer to explore cold starts.'));
}
$('#weight').oninput=()=>$('#weight-value').textContent=pct(Number($('#weight').value));$('#recommend').onclick=recommend;$('#customer').onchange=recommend;
$('#rating-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;try{const id=$('#customer').value;await api('/api/rating','POST',{user_id:Number(id),item_id:Number($('#rating-item').value),rating:Number($('#rating-value').value)});await load(id);notify('Feedback saved. Recommendations updated.')}finally{b.disabled=false}};
$('#evaluate').onclick=async()=>{const b=$('#evaluate');b.disabled=true;notify('Evaluating held-out interactions…');try{const id=$('#customer').value;await api('/api/evaluate','POST');await load(id);notify('Evaluation completed.')}finally{b.disabled=false}};
async function audit(){const rows=await api('/api/audit');$('#audit').replaceChildren(...rows.map(r=>{const li=el('li');li.append(el('h3',r.action),el('small',new Date(r.created).toLocaleString()),el('p',Object.entries(JSON.parse(r.details)).map(([k,v])=>k.replaceAll('_',' ')+': '+v).join(' · ')));return li}))}
$('#audit-refresh').onclick=audit;nav(v=>{if(v==='history')audit()});$('#new-customer').onclick=()=>$('#customer-dialog').showModal();$('#customer-close').onclick=()=>$('#customer-dialog').close();
$('#customer-form').onsubmit=async e=>{e.preventDefault();const r=await api('/api/customers','POST',{name:$('#customer-name').value});$('#customer-dialog').close();await load(r.id);notify('New customer created with no rating history.')};await load();

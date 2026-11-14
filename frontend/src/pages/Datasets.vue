<script setup lang="ts">
import {ref,onMounted} from 'vue';
import {datasets} from '../stores/datasets';
import {canWrite} from '../stores/auth';
import {useTask} from '../hooks/useTask';
import {correctDataset} from '../api/datasets';
import {pct} from '../utils/format';
import PageHeading from '../components/common/PageHeading.vue';
import Notice from '../components/common/Notice.vue';
const name=ref(''),text=ref(''),description=ref(''),selected=ref('demo-dataset');
const target=ref('demo-dataset'),corrections=ref(''),result=ref<any>(null);
const importer=useTask(),correction=useTask();
const labels:Record<string,string>={applied:'已按新版更新',ignored_stale:'旧版已忽略',ignored_replay:'同值重放已忽略'};
onMounted(datasets.load);
async function file(e:Event){const f=(e.target as HTMLInputElement).files?.[0];if(f)text.value=await f.text()}
function submit(){importer.act(async()=>{await datasets.create({name:name.value,csv_text:text.value,description:description.value});name.value='';text.value=''})}
function submitCorrections(){correction.act(async()=>{result.value=await correctDataset(target.value,{csv_text:corrections.value});corrections.value='';await datasets.load()})}
</script>
<template>
<PageHeading index="01 / 原浆检测" title="每种原浆，都有自己的价格与边界。" note="成本单位元/吨；强度为模拟指数0–100，白度0–100%，回收纤维率0–1。中心±扰动宽度必须落在物理范围内。补发更正按每行版本号裁决；已建情景固定在创建时的批次修订。"/>
<div class="two-col">
<section>
<Notice :message="datasets.error.value"/>
<article v-for="r in datasets.items.value" :key="r.id" class="dataset-row">
<button class="record-open" @click="selected=selected===r.id?'':r.id">
<h3>{{r.name}}</h3>
<p>{{r.materials.length}}种 · 修订版次 r{{r.revision||1}} · {{r.description}}</p>
<span>展开检测与供给记录 ↗</span>
</button>
<div v-if="selected===r.id" class="table-wrap">
<table>
<thead><tr><th>原浆</th><th>版本</th><th>成本±幅度</th><th>强度±幅度</th><th>白度±幅度</th><th>回收率±幅度</th><th>供给比例</th></tr></thead>
<tbody><tr v-for="m in r.materials" :key="m.material_id"><td>{{m.name}}</td><td>v{{m.version||1}}</td><td>{{m.cost}}±{{m.cost_width}}</td><td>{{m.strength}}±{{m.strength_width}}</td><td>{{m.whiteness}}±{{m.whiteness_width}}</td><td>{{pct(m.recycled)}}±{{pct(m.recycled_width)}}</td><td>{{pct(m.min_share)}}—{{pct(m.max_share)}}</td></tr></tbody>
</table>
</div>
</article>
</section>
<div v-if="canWrite()" class="editor-stack">
<form class="editor-panel" @submit.prevent="submit">
<h2>导入原浆批次</h2>
<label>批次名称<input v-model="name" required minlength="2"></label>
<label>CSV文件<input type="file" accept=".csv" @change="file"></label>
<label>原浆CSV<textarea v-model="text" rows="9" required placeholder="material_id,name,cost,min_share,max_share,strength,whiteness,recycled,strength_width,whiteness_width,recycled_width,cost_width"></textarea></label>
<label>检测/报价说明<input v-model="description"></label>
<Notice :message="importer.error.value"/>
<button :disabled="importer.busy.value">校验并导入原浆</button>
</form>
<form class="editor-panel" @submit.prevent="submitCorrections">
<h2>补发检测/报价更正</h2>
<label>目标批次<select v-model="target"><option v-for="r in datasets.items.value" :key="r.id" :value="r.id">{{r.name}} · r{{r.revision||1}}</option></select></label>
<label>更正CSV<textarea v-model="corrections" rows="6" required placeholder="material_id,version,cost,strength"></textarea></label>
<p class="method-note">首列material_id与版本号version，其余列为待更正数值，空单元格不变。新版更新，旧版与同值重放忽略，同版异值整批拒绝；任一行非法则整批不落地。</p>
<Notice :message="correction.error.value"/>
<button :disabled="correction.busy.value">按版本裁决并应用更正</button>
<div v-if="result" class="correction-result">
<p>应用 {{result.applied}} · 旧版忽略 {{result.ignored_stale}} · 重放忽略 {{result.ignored_replay}} · 拒绝 {{result.rejected}} · 当前修订 r{{result.revision}}</p>
<ul><li v-for="row in result.rows" :key="row.material_id"><span>{{row.material_id}} · v{{row.version}}</span><span>{{labels[row.disposition]||row.disposition}}</span></li></ul>
</div>
</form>
</div>
<aside v-else class="margin-note">只读账号可以核查原浆参数。导入与补发更正需要分析师权限。</aside>
</div>
</template>

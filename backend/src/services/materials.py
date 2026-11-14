import csv,io,math
from ..constants.enums import PROPERTIES,PHYSICAL_BOUNDS
FIELDS=["material_id","name","cost","min_share","max_share"]+PROPERTIES+[k+"_width" for k in PROPERTIES]+["cost_width"]
CORRECTABLE=FIELDS[2:]

def validate_item(item):
 if not 0<item["cost"]<=1e6 or not 0<=item["cost_width"]<item["cost"]:raise ValueError("成本须为正，成本扰动下界也须为正")
 if not 0<=item["min_share"]<=item["max_share"]<=1:raise ValueError("供给比例须满足0≤下界≤上界≤1")
 for key,(lo,hi) in PHYSICAL_BOUNDS.items():
  value,width=item[key],item[key+"_width"]
  if width<0 or value-width<lo or value+width>hi:raise ValueError(f"{key}的中心±扰动宽度超出物理范围[{lo},{hi}]")

def parse_csv(text):
 rows=list(csv.DictReader(io.StringIO(text)))
 if not 2<=len(rows)<=20 or not set(FIELDS).issubset(rows[0]):raise ValueError("需要2至20种原浆，CSV列名不完整")
 result=[];ids=set()
 for index,row in enumerate(rows,2):
  ident=(row.get("material_id") or "").strip();name=(row.get("name") or "").strip()
  if not ident or len(ident)>60 or ident in ids or not name:raise ValueError(f"第{index}行原浆ID/名称为空、过长或重复")
  ids.add(ident);item={"material_id":ident,"name":name}
  for key in FIELDS[2:]:
   try:value=float(row.get(key))
   except Exception:raise ValueError(f"第{index}行{key}必须为数值")
   if not math.isfinite(value):raise ValueError(f"第{index}行{key}必须有限")
   item[key]=value
  validate_item(item)
  result.append(item)
 return result

def parse_corrections(text):
 rows=list(csv.DictReader(io.StringIO(text)))
 if not 1<=len(rows)<=200:raise ValueError("需要1至200行更正")
 header=set(rows[0])
 if None in header:raise ValueError("更正CSV存在列数不一致的行")
 if not {"material_id","version"}.issubset(header):raise ValueError("更正CSV必须包含material_id与version列")
 extra=header-{"material_id","version"}-set(CORRECTABLE)
 if extra:raise ValueError("更正CSV包含不可更正的列："+",".join(sorted(extra)))
 fields=[key for key in CORRECTABLE if key in header]
 if not fields:raise ValueError("更正CSV至少需要一个可更正数值列")
 result=[];seen=set()
 for index,row in enumerate(rows,2):
  ident=(row.get("material_id") or "").strip()
  if not ident or ident in seen:raise ValueError(f"第{index}行原浆ID为空或在同一更正批次内重复")
  seen.add(ident)
  try:version=float((row.get("version") or "").strip())
  except Exception:raise ValueError(f"第{index}行version必须为数值")
  if not math.isfinite(version) or version<1 or not version.is_integer():raise ValueError(f"第{index}行version必须为正整数")
  changes={}
  for key in fields:
   cell=(row.get(key) or "").strip()
   if cell=="":continue
   try:value=float(cell)
   except Exception:raise ValueError(f"第{index}行{key}必须为数值")
   if not math.isfinite(value):raise ValueError(f"第{index}行{key}必须有限")
   changes[key]=value
  if not changes:raise ValueError(f"第{index}行未提供任何更正数值")
  result.append({"material_id":ident,"version":int(version),"changes":changes})
 return result

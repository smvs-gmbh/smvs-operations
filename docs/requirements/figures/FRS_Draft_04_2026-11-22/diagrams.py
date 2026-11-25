from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import textwrap,math
B=Path(__file__).resolve().parent;OUT=B/'figures';OUT.mkdir(exist_ok=True)
FONT='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
f=ImageFont.truetype(FONT,34);sm=ImageFont.truetype(FONT,30);bold=ImageFont.truetype(BOLD,36)
class Diagram:
 def __init__(self,h):self.im=Image.new('RGB',(1800,h),'white');self.d=ImageDraw.Draw(self.im)
 def box(self,x,y,w,h,text,fill='#f1f1f1',font=f):
  self.d.rounded_rectangle((x,y,x+w,y+h),radius=12,fill=fill,outline='#424242',width=3)
  lines=[]
  for para in text.split('\n'):
   line=''
   for word in para.split():
    cand=(line+' '+word).strip()
    if self.d.textlength(cand,font=font)>w-40:
     lines.append(line);line=word
    else:line=cand
   lines.append(line)
  lineh=font.size+9;assert len(lines)*lineh<=h-20,(text,len(lines),h)
  yy=y+(h-len(lines)*lineh)/2
  for line in lines:
   self.d.text((x+(w-self.d.textlength(line,font=font))/2,yy),line,font=font,fill='black');yy+=lineh
 def arrow(self,points,label='',at=None):
  self.d.line(points,fill='#424242',width=4)
  a,b=points[-2:];theta=math.atan2(b[1]-a[1],b[0]-a[0]);L=19
  self.d.polygon([b,(b[0]-L*math.cos(theta-.45),b[1]-L*math.sin(theta-.45)),(b[0]-L*math.cos(theta+.45),b[1]-L*math.sin(theta+.45))],fill='#424242')
  if label:
   x,y=at;bb=self.d.textbbox((x,y),label,font=sm);self.d.rectangle((bb[0]-5,bb[1]-4,bb[2]+5,bb[3]+4),fill='white');self.d.text((x,y),label,font=sm,fill='black')
 def association(self,points):
  # Annotation association: dashed, explicitly without an arrowhead.
  for start,end in zip(points,points[1:]):
   length=math.hypot(end[0]-start[0],end[1]-start[1])
   if not length:continue
   ux=(end[0]-start[0])/length;uy=(end[1]-start[1])/length
   for offset in range(0,math.ceil(length),24):
    stop=min(offset+13,length)
    self.d.line([(start[0]+ux*offset,start[1]+uy*offset),(start[0]+ux*stop,start[1]+uy*stop)],fill='#555555',width=3)
 def save(self,name):self.im.save(OUT/(name+'.png'),dpi=(300,300))
def vertical(name,steps,notes,h=1410):
 d=Diagram(h);x=55;w=1080;y=35;bh=155;gap=55
 for i,text in enumerate(steps):
  yy=y+i*(bh+gap);d.box(x,yy,w,bh,text)
  if i<len(steps)-1:d.arrow([(x+w/2,yy+bh),(x+w/2,yy+bh+gap)])
 for y,h,text,target in notes:
  d.box(1240,y,515,h,text,fill='white',font=sm)
  if target is not None:d.association([(1240,y+h/2),(1188,y+h/2),(1188,target),(1135,target)])
 d.save(name)
vertical('01_passkeys',[
 'Administrator creates named user\nSelect Administrator and/or NMVO User',
 'Single-use enrolment invitation\n24-hour lifetime; trusted delivery channel',
 'Recipient registers a passkey\nDiscoverable credential and user verification',
 'Server verifies WebAuthn response\nBrowser challenge, RP ID, origin and verification',
 'Consume challenge and invitation\nStore public credential and issue session',
 'Server-side session and role checks\n8-hour lifetime; protect reads and changes'],[
 (35,220,'Bootstrap first administrator through the trusted server console.',112),
 (325,220,'Later sign-in: new challenge and passkey assertion; no password login.',745),
 (690,215,'Invalid, expired or replayed response: refuse sign-in; no session.',745),
 (1020,300,'Disable user or change roles: revoke tokens and sessions. A backup passkey requires recent sign-in.',1160)])
vertical('02_connect',[
 'Registrant submits Tally form\nSigned webhook reaches public Connect relay',
 'Relay checks signature and format\nFixed TLS route to the private registration API',
 'Private API checks peer and bearer\nValidate signature and commit receipt plus CRM',
 'Awaiting email confirmation\nInternal mail process sends single-use link',
 'Recipient confirms by explicit POST\nConsume token; move registration to Needs review',
 'Staff reviews identity and duplicates\nApprove to Ready for NMVS; record external ID'],[
 (35,210,'Public relay is stateless: no database or mail credentials.',322),
 (315,250,'Failed or uncertain internal commit: return unavailable, never received. Retry is deduplicated.',535),
 (730,260,'Reject with reason; expire private security data; resend only through controlled internal workflow.',1160),
 (1050,245,'NMVS creation is external. Recording its organisation ID does not call an NMVS create operation.',1160)])
vertical('03_rca',[
 'Select Alert and source revision\nRetain source identity, pack and market context',
 'Confirm responsibility and evidence\nCH / LI / foreign / unconfirmed; read-only checks',
 'Review evidence and applicable Findings\nEnd User and/or MAH, Pack Audit Trail, upload scope',
 'Authorised staff records assessment\nOrigin, reason and follow-up; individual or batch',
 'Recheck source, Findings and review state\nReject stale confirmation; lock affected records',
 'Save local decision and event history\nSource revision, actor, Findings and resolution basis'],[
 (35,235,'Unconfirmed responsibility blocks closure. Foreign support completion is distinct from local closure.',322),
 (345,235,'Snapshot counts are supporting context, not proof of a historical upload or pack status.',535),
 (735,250,'Batch action: preview exact groups, select explicitly, then revalidate the confirmed scope.',955),
 (1080,210,'No change to NMVS pack state. External Hub status remains separately attributed.',1160)])
d=Diagram(1160)
d.box(35,40,490,280,'NMVS reports\nDaily Snapshot\nExceptions / activity\nPack audit / upload',font=f)
d.box(35,395,490,205,'Refdata SAI\nSwiss product names\nand MAH reference',font=f)
d.box(35,700,490,300,'Other paths\nConnect and staff CRM\nuse separate workflows.\nHub / VerifyIt feed scope\nis release-dependent.',fill='white',font=sm)
steps=[('Acquire and retain raw bytes\njob, hash, source and report metadata',40),('Parse and validate source structure\nRecord attempt and failure stage',260),('Stage accepted datasets and rows\nHeaders, order, raw JSON and row hashes',480),('Validate mapping and publish\nProduct/Batch + SAI; separate report paths',700),('Operational views and RCA\nSource scope, coverage and provenance',920)]
for t,y in steps:d.box(680,y,1070,165,t)
for i in range(4):d.arrow([(1215,steps[i][1]+165),(1215,steps[i+1][1])])
d.arrow([(525,180),(590,180),(590,122),(680,122)])
d.arrow([(525,490),(625,490),(625,122),(680,122)])
d.save('04_information_flow')
# Actual selected foreign-key relations. Parent-to-child arrows marked one-to-many.
d=Diagram(1210)
boxes={
 'job':(45,25,740,150,'integration_jobs\nid PK; source, request scope, status'),
 'content':(1005,25,740,150,'artifact_contents\nid PK; SHA-256, original bytes'),
 'artifact':(45,270,740,170,'acquired_artifacts\nid PK; integration_job_id FK\ncontent_id FK; source/report identity'),
 'run':(1005,270,740,170,'processing_runs\nid PK; artifact_id FK\nparser version, attempt and failure'),
 'dataset':(1005,610,740,170,'staging_datasets\nid PK; processing_run_id FK\nartifact_id FK; headers and row count'),
 'row':(1005,960,740,170,'staging_rows\nid PK; staging_dataset_id FK\nsource row number, hash and raw JSON')}
for v in boxes.values():d.box(*v,font=sm)
d.arrow([(415,175),(415,270)],'1 : N',(440,205))
d.arrow([(1005,100),(890,100),(890,355),(785,355)],'1 : N',(805,220))
d.arrow([(785,390),(1005,390)],'1 : N',(810,345))
d.arrow([(1375,440),(1375,610)],'1 : N',(1400,500))
d.arrow([(785,405),(875,405),(875,695),(1005,695)],'1 : N',(895,630))
d.arrow([(1375,780),(1375,960)],'1 : N',(1400,850))
d.box(45,690,740,370,'Selected physical MySQL model\nArrows: parent to referencing child.\nPK/FK links come from ORM models.\nOnly relevant fields are shown;\nnot a complete schema export.',fill='white',font=sm)
d.save('05_staging_model')
d=Diagram(1300)
# compact actual product and SAI business-entity links
for x,y,t in [(40,25,'products\nid PK'),(40,270,'product_source_records\nid PK; product_id FK'),(40,525,'product_versions\nid PK; product_source_id FK'),(40,790,'batches\nproduct_source_id FK\nproduct_version_id FK'),(1050,25,'sai_holders\nid PK'),(1050,270,'sai_preparations\nid PK; holder_id FK'),(1050,525,'sai_packages\nid PK; preparation_id FK'),(1050,790,'product_reference_matches\nproduct_id PK and FK\nsai_package_id optional FK')]:d.box(x,y,710,155,t,font=sm)
for x in [395,1405]:
 for y in [180,425,680]:d.arrow([(x,y),(x,y+90)],'1 : N'if y<680 else('1 : N'if x==395 else'0..1 match target'),(x+15,y+25))
# Above the last SAI arrow is child -> match (one package may be referenced by many product matches): correct label.
# replace this particular label area deterministically by drawing the precise relationship label.
d.d.rectangle((1415,700,1770,745),fill='white');d.d.text((1420,705),'1 : N',font=sm,fill='black')
d.arrow([(750,100),(900,100),(900,850),(1050,850)],'1 : 0..1',(790,770))
d.arrow([(40,350),(15,350),(15,865),(40,865)])
d.box(40,1070,1720,175,'Mapping provenance: mapping_runs references selected Snapshot and SAI processing_runs.\ncurrent_publications selects the accepted product-batch mapping. Other report and participant\npublications have separate tables; a snapshot job is not one global atomic publication.',fill='white',font=sm)
d.save('06_product_model')
print('Six diagrams created')

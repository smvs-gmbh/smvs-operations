from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
import ast,math,textwrap
B=Path(__file__).resolve().parent;OUT=B/'figures';OUT.mkdir(exist_ok=True)
FONT='/System/Library/Fonts/Supplemental/Arial.ttf';BOLD='/System/Library/Fonts/Supplemental/Arial Bold.ttf'
f=ImageFont.truetype(FONT,32);sm=ImageFont.truetype(FONT,28);bold=ImageFont.truetype(BOLD,34)
src=Path('/Users/reinhold/Documents/Development/smvs-operations/docs/requirements/figures/FRS_Draft_04_2026-11-22/diagrams.py')
a=ast.parse(src.read_text());nodes=[n for n in a.body if isinstance(n,ast.ClassDef)or isinstance(n,ast.FunctionDef)]
exec(compile(ast.Module(body=nodes,type_ignores=[]),'diagram_helpers','exec'),globals())
d=Diagram(1330);d.im=Image.new('RGB',(2000,1330),'white');d.d=ImageDraw.Draw(d.im)
d.d.rounded_rectangle((35,295,1965,1250),radius=18,outline='#707070',width=3)
d.d.text((65,310),'SMVS Operations',font=sm,fill='#222222')
for x,t in [(80,'NMVS: Identity / Exceptions /\nReport APIs\nSwiss reference data (SAI)'),(740,'Staff browser\nAdministrator / normal user'),(1400,'Registration form\nAlert Desk participant browser')]:d.box(x,45,520,150,t,fill='white')
d.box(80,410,520,170,'Integration worker\nScheduler, source clients\nand parsers')
d.box(740,410,520,170,'Operations portal\nCRM, registrations,\nreports and RCA')
d.box(1400,410,520,170,'Separate browser gateways\nConnect relay\nAlert Desk local pilot')
d.box(1400,730,520,150,'Private command APIs\nRegistration intake\nParticipant access / Findings')
d.box(740,730,520,150,'Internal mail process\nConfirmation outbox\nand temporary-data cleanup')
d.box(100,1060,1800,150,'Relational application database\nOriginal reports and staging • Published operational data • CRM and registrations • Cases, Findings and review history',font=f)
for x in [340,1000,1660]:d.arrow([(x,195),(x,410)])
d.arrow([(340,580),(340,1060)],'Reports and mapped results',(65,960))
d.arrow([(1260,490),(1320,490),(1320,1060)])
d.arrow([(1300,1060),(1300,555),(1260,555)])
d.arrow([(1660,580),(1660,730)],'Fixed commands',(1480,645))
d.arrow([(1660,880),(1660,1060)],'Case records',(1430,960))
d.arrow([(1640,1060),(1640,880)])
d.arrow([(1000,1060),(1000,880)],'Pending mail',(1030,945))
d.arrow([(950,880),(950,1060)])
d.d.text((65,1270),'Logical design only. Alert Desk paths are local-pilot code; deployment status is recorded separately.',font=sm,fill='#333333')
d.save('01_architecture')
vertical('02_passkeys',[
 'Administrator creates a named account\nNormal user; administrator rights when needed',
 'Single-use enrolment invitation\n24-hour lifetime; trusted delivery channel',
 'Recipient registers a passkey\nAuthenticator verifies its user',
 'Portal verifies passkey response\nConfigured website, challenge and active account',
 'Consume invitation and challenge\nStore public credential and create session',
 'Normal operational access\nAdministrator actions checked separately'],[
 (35,220,'First Administrator is created through the trusted server console.',112),
 (325,220,'Later sign-in uses a fresh challenge and registered passkey. No password fallback.',745),
 (690,215,'Invalid, expired or reused response: refuse sign-in; no session.',745),
 (1020,300,'Disabling an account or changing access cancels tokens and sessions. Additional passkey requires recent sign-in.',1160)])
for old,new in [('03_rca','04_rca')]:
 (OUT/(new+'.png')).write_bytes((src.parent/(old+'.png')).read_bytes())
vertical('03_connect',[
 'Registrant submits registration form\nSigned message reaches public Connect relay',
 'Relay checks signature and format\nFixed TLS route to the private registration API',
 'Private API checks peer and bearer\nValidate signature and commit receipt plus CRM',
 'Awaiting email confirmation\nInternal mail process sends single-use link',
 'Recipient confirms by explicit POST\nConsume token; move registration to Needs review',
 'Staff reviews identity and duplicates\nApprove to Ready for NMVS; record external ID'],[
 (35,210,'Public relay is stateless: no database or mail credentials.',322),
 (315,250,'Failed or uncertain internal commit: return unavailable, never received. Retry is deduplicated.',535),
 (730,260,'Reject with reason; expire private security data; resend only through controlled internal workflow.',1160),
 (1050,245,'NMVS creation is external. Recording its organisation ID does not call an NMVS create operation.',1160)])
(OUT/'01_architecture.mmd').write_text('''flowchart TB
  sources["NMVS Identity API / Exceptions API / Report API / SAI"] --> worker
  staff["Staff: Administrator / normal user"] --> portal
  browsers["Registration form / participant browser"] --> gateways
  subgraph ops["SMVS Operations logical components"]
    worker["Integration worker / scheduler / parsers"] --> db
    portal["Operations portal: CRM / registration / reports / RCA"] <--> db
    gateways["Connect relay / Alert Desk local-pilot gateway"] --> apis
    apis["Private registration and participant APIs"] <--> db
    db[("Relational application database")]
    db <--> mail["Internal confirmation mail process / cleanup"]
  end
''')
print('Created four figures and architecture Mermaid source')

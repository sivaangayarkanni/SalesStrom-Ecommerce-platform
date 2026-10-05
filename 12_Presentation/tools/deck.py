# SALESTORM deck generator (python-pptx). Run: python3 deck.py
import os, qrcode
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE, MSO_CONNECTOR
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LEGEND_POSITION, XL_LABEL_POSITION
from PIL import Image
R=os.environ.get('SALESTORM_ROOT','/workspace/SALESTORM_TEAM/')
BG=RGBColor(0x0B,0x12,0x20); BAR=RGBColor(0x10,0x1A,0x2E); CARD=RGBColor(0x15,0x20,0x38); CARD2=RGBColor(0x1E,0x2B,0x48)
WHITE=RGBColor(255,255,255); MUTED=RGBColor(0x9A,0xA8,0xC2)
CY=RGBColor(0x22,0xD3,0xEE); AM=RGBColor(0xF5,0x9E,0x0B); GR=RGBColor(0x10,0xB9,0x81); RD=RGBColor(0xEF,0x44,0x44); PU=RGBColor(0xA7,0x8B,0xFA); BL=RGBColor(0x3B,0x82,0xF6); TE=RGBColor(0x14,0xB8,0xA6)
F='Segoe UI'
p=Presentation(); p.slide_width=Inches(13.333); p.slide_height=Inches(7.5)
SW,SH=13.333,7.5
LIVE='https://sivaangayarkanni.github.io/SalesStrom-Ecommerce-platform/'
REPO='github.com/sivaangayarkanni/SalesStrom-Ecommerce-platform'
def rect(s,x,y,w,h,fill,shape=MSO_SHAPE.ROUNDED_RECTANGLE,line=None,adj=0.08):
    sh=s.shapes.add_shape(shape,Inches(x),Inches(y),Inches(w),Inches(h))
    sh.fill.solid(); sh.fill.fore_color.rgb=fill
    if line: sh.line.color.rgb=line; sh.line.width=Pt(1.5)
    else: sh.line.fill.background()
    if shape==MSO_SHAPE.ROUNDED_RECTANGLE: sh.adjustments[0]=adj
    sh.shadow.inherit=False
    return sh
def txt(s,x,y,w,h,text,size=16,color=WHITE,bold=False,align=PP_ALIGN.LEFT,anchor=MSO_ANCHOR.TOP,font=F,sp=6):
    tb=s.shapes.add_textbox(Inches(x),Inches(y),Inches(w),Inches(h)); tf=tb.text_frame; tf.word_wrap=True
    tf.vertical_anchor=anchor; tf.margin_left=tf.margin_right=Inches(0.05); tf.margin_top=tf.margin_bottom=Inches(0.03)
    lines=text if isinstance(text,list) else [text]
    for i,l in enumerate(lines):
        para=tf.paragraphs[0] if i==0 else tf.add_paragraph(); para.alignment=align
        segs=l if isinstance(l,list) else [(l,color,bold)]
        for t,c,b in segs:
            r=para.add_run(); r.text=t; r.font.size=Pt(size); r.font.color.rgb=c; r.font.bold=b; r.font.name=font
        para.space_after=Pt(sp)
    return tb
n=0
def notes(s,say,q=None,a=None):
    t='SAY: '+say
    if q: t+='\n\nLIKELY JUDGE QUESTION: '+q+'\nANSWER: '+a
    s.notes_slide.notes_text_frame.text=t
def base(title=None,kicker=None,accent=CY):
    global n; n+=1
    s=p.slides.add_slide(p.slide_layouts[6])
    s.background.fill.solid(); s.background.fill.fore_color.rgb=BG
    if title:
        rect(s,0,0,SW,1.25,BAR,MSO_SHAPE.RECTANGLE); rect(s,0,1.25,SW,0.04,accent,MSO_SHAPE.RECTANGLE)
        rect(s,0.6,0.3,0.1,0.72,accent,MSO_SHAPE.RECTANGLE)
        if kicker: txt(s,0.85,0.22,9,0.35,kicker.upper(),12,accent,True)
        txt(s,0.85,0.5,11.6,0.7,title,28,WHITE,True)
        txt(s,11.3,0.25,1.5,0.35,'SALESTORM',11,MUTED,True,PP_ALIGN.RIGHT)
    else:
        rect(s,0,0,SW,0.08,CY,MSO_SHAPE.RECTANGLE)
    rect(s,0.6,7.0,12.13,0.012,CARD2,MSO_SHAPE.RECTANGLE)
    txt(s,0.6,7.06,6,0.3,'SALESTORM • SysCrafters 2026',10,MUTED)
    txt(s,11.5,7.06,1.23,0.3,f'{n:02d}',10,accent,True,PP_ALIGN.RIGHT)
    return s
def img(s,path,x,y,w,h,card=True,pad=0.12):
    if card: rect(s,x,y,w,h,WHITE,adj=0.03)
    iw,ih=Image.open(path).size; bw,bh=w-2*pad,h-2*pad
    sc=min(bw/iw,bh/ih); dw,dh=iw*sc,ih*sc
    s.shapes.add_picture(path,Inches(x+pad+(bw-dw)/2),Inches(y+pad+(bh-dh)/2),Inches(dw),Inches(dh))
def stat(s,x,y,w,h,num,label,accent,ns=34,ls=13):
    rect(s,x,y,w,h,CARD); rect(s,x,y,0.09,h,accent,MSO_SHAPE.RECTANGLE)
    txt(s,x+0.25,y+0.08,w-0.3,h*0.55,num,ns,accent,True)
    txt(s,x+0.25,y+h*0.56,w-0.3,h*0.44,label,ls,MUTED)
def card(s,x,y,w,h,head,body,accent=CY,size=13,hs=16):
    rect(s,x,y,w,h,CARD); rect(s,x,y,w,0.07,accent,MSO_SHAPE.RECTANGLE)
    txt(s,x+0.2,y+0.16,w-0.4,0.45,head,hs,WHITE,True)
    txt(s,x+0.2,y+0.62,w-0.4,h-0.7,body,size,MUTED)
def icon(s,x,y,d,ch,c,size=16):
    rect(s,x,y,d,d,c,MSO_SHAPE.OVAL); txt(s,x,y,d,d,ch,size,BG,True,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE)
def chip(s,x,y,t,c,w=None,size=12):
    w=w or 0.13*len(t)+0.45
    sh=rect(s,x,y,w,0.38,CARD2,line=c,adj=0.5); tf=sh.text_frame; tf.margin_top=tf.margin_bottom=0; tf.margin_left=tf.margin_right=Inches(0.05)
    tf.paragraphs[0].alignment=PP_ALIGN.CENTER; r=tf.paragraphs[0].add_run(); r.text=t; r.font.size=Pt(size); r.font.color.rgb=c; r.font.bold=True; r.font.name=F
    return w
def divider(num,title,sub,c,owner):
    s=base(); 
    rect(s,8.2,-1.5,7.5,7.5,CARD,MSO_SHAPE.OVAL); rect(s,9.6,3.6,5,5,CARD2,MSO_SHAPE.OVAL)
    txt(s,0.9,1.7,4,1.6,num,110,c,True)
    rect(s,0.95,3.55,1.6,0.08,c,MSO_SHAPE.RECTANGLE)
    txt(s,0.9,3.8,9,1,title,44,WHITE,True)
    txt(s,0.9,4.75,9,0.8,sub,18,MUTED)
    chip(s,0.9,5.8,'Owner: '+owner,c)
    return s
def table(s,x,y,w,rows,colw,rh=0.5,hdr=CY,size=12):
    shp=s.shapes.add_table(len(rows),len(colw),Inches(x),Inches(y),Inches(w),Inches(rh*len(rows)))
    t=shp.table
    for j,cw in enumerate(colw): t.columns[j].width=Inches(cw)
    for i,row in enumerate(rows):
        t.rows[i].height=Inches(rh)
        for j,val in enumerate(row):
            c=t.cell(i,j); c.fill.solid(); c.fill.fore_color.rgb=(CARD2 if i==0 else (CARD if i%2 else BAR))
            c.margin_left=c.margin_right=Inches(0.08); c.margin_top=c.margin_bottom=Inches(0.02); c.vertical_anchor=MSO_ANCHOR.MIDDLE
            tf=c.text_frame; tf.word_wrap=True; para=tf.paragraphs[0]; para.text=''
            r=para.add_run(); r.text=val; r.font.name=F; r.font.size=Pt(size)
            r.font.color.rgb=hdr if i==0 else (WHITE if j==0 else MUTED); r.font.bold=(i==0 or j==0)
    return t
def style_chart(ch,size=12):
    ch.font.size=Pt(size); ch.font.color.rgb=WHITE; ch.font.name=F
    for ax in (ch.category_axis,ch.value_axis):
        ax.tick_labels.font.color.rgb=MUTED; ax.tick_labels.font.size=Pt(size); ax.format.line.color.rgb=CARD2
    ch.value_axis.major_gridlines.format.line.color.rgb=CARD2
def bar(s,x,y,w,h,cats,series,colors,title=None,legend=True,fmt='#,##0',horiz=False,size=12):
    cd=CategoryChartData(); cd.categories=cats
    for nm,vals in series: cd.add_series(nm,vals)
    gf=s.shapes.add_chart(XL_CHART_TYPE.BAR_CLUSTERED if horiz else XL_CHART_TYPE.COLUMN_CLUSTERED,Inches(x),Inches(y),Inches(w),Inches(h),cd)
    ch=gf.chart; style_chart(ch,size)
    ch.has_legend=legend and len(series)>1
    if ch.has_legend: ch.legend.position=XL_LEGEND_POSITION.BOTTOM; ch.legend.include_in_layout=False; ch.legend.font.color.rgb=MUTED; ch.legend.font.size=Pt(size)
    if title: ch.has_title=True; ch.chart_title.text_frame.text=title; tp=ch.chart_title.text_frame.paragraphs[0]; tp.runs[0].font.size=Pt(size+2); tp.runs[0].font.color.rgb=WHITE; tp.runs[0].font.bold=True
    else: ch.has_title=False
    pl=ch.plots[0]; pl.gap_width=60; pl.overlap=-10 if len(series)>1 else 0
    pl.has_data_labels=True; dl=pl.data_labels; dl.number_format=fmt; dl.number_format_is_linked=False; dl.font.color.rgb=WHITE; dl.font.size=Pt(size); dl.font.bold=True; dl.position=XL_LABEL_POSITION.OUTSIDE_END
    for i,ser in enumerate(pl.series):
        ser.format.fill.solid(); ser.format.fill.fore_color.rgb=colors[i] if len(series)>1 else colors[0]
        if len(series)==1 and len(colors)>1:
            for k,c in enumerate(colors):
                pt=ser.points[k]; pt.format.fill.solid(); pt.format.fill.fore_color.rgb=c
    return ch
TAG=lambda c=WHITE: [[('Caches can say ',c,False),('NO',RD,True),('. Only the database can say ',c,False),('YES',GR,True),('.',c,False)]]
D2=R+'02_HLD/drawio/'; D3=R+'03_LLD/drawio/'

# 1 Title
s=base()
rect(s,-1.5,4.4,8,8,CARD2,MSO_SHAPE.OVAL); rect(s,9.3,-2.6,6.5,6.5,CARD,MSO_SHAPE.OVAL)
for i,c in enumerate([BL,CY,TE,PU,AM]):
    rect(s,10.5+i*0.55,4.3-i*0.45,0.42,0.45+i*0.45+1.2,c,adj=0.2)
txt(s,0.8,1.2,10,0.4,'SYSCRAFTERS 2026  •  SYSTEM DESIGN HACKATHON',14,CY,True)
txt(s,0.8,1.65,9,1.3,'SALESTORM',72,WHITE,True)
txt(s,0.8,2.95,8.6,0.7,'Selling exactly 100 units to 10,000 buyers in one second',24,MUTED)
txt(s,0.8,3.75,8.6,0.6,TAG(),22)
x=0.8
for t,c,w in [('Cache-Hit Ladder',CY,2.2),('0 oversold',GR,1.5),('Exactly-once charge',AM,2.45),('Survives 30 s outage',PU,2.55)]:
    x+=chip(s,x,4.75,t,c,w)+0.2
txt(s,0.8,5.5,8,0.4,'Flash-sale e-commerce platform  •  HLD • LLD • DB • API • Reliability • Proof',13,MUTED)
notes(s,'We are SALESTORM. We built a flash-sale platform that sells exactly 100 units to 10,000 simultaneous buyers, never charges twice, and survives a 30-second Order Service outage. One sentence sums up the design: caches can say NO, only the database can say YES.',
 'What is the one idea we should remember?','The Cache-Hit Ladder: every tier may reject, only a committed Postgres transaction may accept — speed from caches, correctness from the DB.')

# 2 Problem in numbers
s=base('The problem in numbers','Problem',RD)
for i,(nu,l,c) in enumerate([('100','units in stock',CY),('10,000','buyers click at once',AM),('500k','requests / s at peak',PU)]):
    stat(s,0.6+i*4.1,1.6,3.9,1.75,nu,l,c,44,15)
for i,(nu,l,c) in enumerate([('95 / 5','% payments succeed / fail',GR),('2%','duplicate requests (double clicks, retries)',BL),('30 s','Order Service outage mid-sale',RD)]):
    stat(s,0.6+i*4.1,3.6,3.9,1.75,nu,l,c,44,15)
rect(s,0.6,5.65,12.13,1.1,CARD2)
txt(s,0.85,5.75,11.7,0.9,[[('Win condition: ',AM,True),('exactly 100 sold, nobody charged twice, no paid order lost — under all six conditions at once.',WHITE,False)]],18,anchor=MSO_ANCHOR.MIDDLE)
notes(s,'These six numbers are the test case. 100 units, 10,000 buyers, 500k requests per second at peak, 5% payment failures, 2% duplicates and a 30-second outage, all at once.',
 'Why design for 500k req/s if only 100 units sell?','Because demand is set by buyers, not stock: page views and Buy clicks arrive anyway. The ladder absorbs them before they reach the database.')

# 3 Naive design
s=base('What breaks in a naive design','Problem',RD)
card(s,0.6,1.6,4.0,2.4,'Naive flow',['1. SELECT stock','2. if stock > 0: INSERT order','3. UPDATE stock = stock − 1'],RD,15)
card(s,0.6,4.2,4.0,2.55,'Why it fails',['Read-then-write race (write skew)','Retries double-charge','Order down = paid order lost','One hot row = lock queue'],AM,14)
ch=bar(s,4.9,1.5,4.6,5.3,['Naive counter','SALESTORM'],[('Units sold',(650,100))],[RD,GR],title='Units sold (stock = 100)')
rect(s,9.8,1.6,2.93,5.15,CARD)
txt(s,9.95,1.8,2.7,1,'650',60,RD,True,PP_ALIGN.CENTER)
txt(s,9.95,2.9,2.7,0.5,'sold by the naive design',13,MUTED,align=PP_ALIGN.CENTER)
txt(s,9.95,3.6,2.7,1,'+550',40,AM,True,PP_ALIGN.CENTER)
txt(s,9.95,4.45,2.7,0.5,'oversold units = refunds + angry buyers',13,MUTED,align=PP_ALIGN.CENTER)
txt(s,9.95,5.4,2.7,1,'Same 10,200 requests, same simulator',12,CY,True,PP_ALIGN.CENTER)
notes(s,'We ran the naive design through the same simulator with the same 10,200 requests: it sold 650 units of a 100-unit stock. Read-then-write is a race; everything after this slide is about closing it.',
 'Would a transaction fix the naive version?','Not at READ COMMITTED: two transactions both read stock=1 and both write — classic write skew. We fix it structurally with unit rows + SKIP LOCKED + UNIQUE.')

# 4 Requirements
s=base('Requirements: hard guarantees vs targets','Requirements',GR)
card(s,0.6,1.6,5.95,5.15,'Hard guarantees — never break',[],GR)
for i,(t,d) in enumerate([('Never sell unit #101','unit rows + CHECK'),('Never charge twice','Idempotency-Key + UNIQUE'),('Never lose a paid order','outbox + inbox'),('One unit per customer','UNIQUE(sale, customer)')]):
    icon(s,0.85,2.35+i*1.08,0.6,'✓',GR,18); txt(s,1.6,2.3+i*1.08,4.8,0.4,t,17,WHITE,True); txt(s,1.6,2.68+i*1.08,4.8,0.35,d,12,MUTED)
card(s,6.78,1.6,5.95,5.15,'Targets — degrade gracefully',[],AM)
for i,(t,d) in enumerate([('p99 reserve < 200 ms','at 10k req/s normal'),('500k req/s peak','absorbed at CDN + L2'),('99.95% availability','cell isolation, shedding'),('Reservation hold 5 min','TTL + sweeper w/ fencing')]):
    icon(s,7.03,2.35+i*1.08,0.6,'◎',AM,16); txt(s,7.78,2.3+i*1.08,4.8,0.4,t,17,WHITE,True); txt(s,7.78,2.68+i*1.08,4.8,0.35,d,12,MUTED)
notes(s,'We split requirements in two: correctness guarantees enforced by the database that never bend, and performance targets that can degrade gracefully by shedding load.',
 'What do you sacrifice under overload?','Latency and availability of NO answers (503 + Retry-After), never correctness. A rejected buyer can retry; an oversold unit cannot be undone.')

# 5 Ladder
s=base('Unique factor: the Cache-Hit Ladder','Our idea',CY)
tiers=[('L0','Browser','Countdown, assets, Buy debounce','blocks repeat clicks',BL),('L1','CDN + WAF','Product pages + SOLD_OUT flag','9,921 answered',CY),('L2','In-process cache','Hot product & sold-out flag per pod','163 answered',TE),('L3','Redis','100 admission tokens + idempotency keys','7 rejected • 2 replayed',PU),('L4','Postgres','Unit rows • SKIP LOCKED • UNIQUE','107 reached → 100 sold',AM)]
for i,(l,nm,d_,st,c) in enumerate(tiers):
    y=1.55+i*1.0; w=11.9-i*0.9; x=0.7+i*0.45
    rect(s,x,y,w,0.86,CARD); rect(s,x,y,1.0,0.86,c,adj=0.15)
    txt(s,x,y,1.0,0.86,l,24,BG,True,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE)
    txt(s,x+1.2,y+0.06,3.4,0.4,nm,18,WHITE,True); txt(s,x+1.2,y+0.45,4.6,0.4,d_,12,MUTED)
    txt(s,x+w-3.7,y,3.5,0.86,st,16,c,True,PP_ALIGN.RIGHT,MSO_ANCHOR.MIDDLE)
rect(s,0.7,6.6,11.9,0.35,BG,MSO_SHAPE.RECTANGLE)
txt(s,0.7,6.55,11.9,0.4,TAG(MUTED),15,align=PP_ALIGN.CENTER)
notes(s,'Of 10,200 requests, 9,921 were answered at the CDN, 163 at the in-process cache, 7 rejected and 2 replayed at Redis, and only 107 ever touched Postgres, which sold exactly 100. Every tier may say NO; only the DB says YES.',
 'What if a cache is stale and says IN_STOCK?','Harmless: a stale YES only forwards the request to the next tier. The final YES is still a committed DB row. A stale NO is bounded by 1 s TTL and purged on StockReleased.')

# 6 Divider HLD
s=divider('01','High-Level Design','Context → architecture → containers → components → deployment',CY,'Student 1 — System Architect')
notes(s,'Section one: the high-level design, presented by our System Architect.')

# 7-11 HLD diagrams
s=base('System context','HLD • C4 level 1',CY); img(s,D2+'system_context.png',0.6,1.5,8.4,5.35)
card(s,9.2,1.5,3.53,5.35,'Actors & externals',['• Buyers (web / mobile)','• Admin: sale config','• Payment gateway (Razorpay / Stripe)','• Delivery partner','• SMS / e-mail provider','','One system boundary; every external call is behind an adapter + breaker.'],CY,13)
notes(s,'At the context level SALESTORM talks to buyers, admins, a payment gateway, delivery partners and notification providers. Every external dependency sits behind an adapter with a circuit breaker.',
 'What if the payment gateway is down?','The breaker opens, buyers keep their reservation and see a retry message; auths that time out are voided by reconciliation; units return to the pool after TTL.')
s=base('High-level architecture','HLD',CY); img(s,D2+'hld_architecture.png',0.6,1.5,12.13,5.35)
notes(s,'Requests flow browser → CDN/WAF → load balancer → API gateway → stateless services. Redis holds admission tokens, Postgres is the source of truth, Kafka carries events via the outbox to Order, Shipment and Notification.',
 'Why not just add more servers?','The bottleneck is one contested resource — 100 units — not CPU. More servers add more contention; the ladder removes contention by rejecting early.')
s=base('Container view','HLD • C4 level 2',CY); img(s,D2+'container.png',0.6,1.5,12.13,5.35)
notes(s,'Containers: Reservation, Payment, Order, Shipment and Notification services, each owning its data; Redis, Postgres and Kafka are shared infrastructure inside the flash-sale cell.',
 'Is this microservices for its own sake?','No — the split follows failure isolation: Order can be down 30 s without blocking reservations or payments.')
s=base('Component view','HLD • C4 level 3',CY); img(s,D2+'component.png',0.6,1.5,12.13,5.35)
notes(s,'Inside the Reservation service: idempotency filter, token pool, unit repository, outbox writer and the expiry sweeper with a lease and fencing token.',
 'Where is idempotency enforced?','At the edge of the service (idempotency_record) and again in the DB via UNIQUE constraints — two independent layers.')
s=base('Deployment & cell isolation','HLD • Deployment',CY); img(s,D2+'deployment.png',0.6,1.5,8.4,5.35)
for i,(nu,l,c) in enumerate([('1','dedicated flash-sale cell',CY),('<70%','target utilisation per tier',AM),('200','requests in flight (Little\'s law)',PU),('40','Postgres connection pool',GR)]):
    stat(s,9.2,1.5+i*1.37,3.53,1.22,nu,l,c,30,12)
notes(s,'The flash sale runs in its own cell so a meltdown cannot touch normal shopping. We size with Little\'s law: about 200 requests in flight, a DB pool of 40, and stay under 70% utilisation.',
 'Why a separate cell?','Blast radius: if the sale melts down, the regular catalogue and checkout keep running. ADR-010.')

# 12 Divider LLD
s=divider('02','Low-Level Design','Classes • SOLID • patterns • sequences • state machines',PU,'Student 2 — LLD & Design Engineer')
notes(s,'Section two: low-level design, presented by our LLD engineer.')
s=base('Class diagram','LLD',PU); img(s,D3+'class_diagram.png',0.6,1.5,12.13,5.35)
notes(s,'Core classes: CheckoutFacade, ReservationService, TokenPool, InventoryUnitRepository, PaymentService with gateway adapters, plus resilience classes like RetryBudget, LoadShedder, SingleflightCache, HotKeySaltedTokenPool and InboxDeduplicator.',
 'Which class guarantees no oversell?','InventoryUnitRepository.claim() — SELECT … FOR UPDATE SKIP LOCKED on unit rows, backed by DB constraints.')
s=base('SOLID mapping','LLD • Principles',PU)
table(s,0.6,1.55,12.13,[('Principle','Where in SALESTORM','Effect'),
 ('S  Single responsibility','ReservationService (stock) • PaymentService (money) • OrderService (lifecycle)','SMS change never touches payment code'),
 ('O  Open / closed','PricingStrategy, PaymentGateway adapters, HotKeySaltedTokenPool','New provider = new class, core unchanged'),
 ('L  Liskov substitution','Razorpay, Stripe, CircuitBreakerGateway honour one contract','PaymentService works with any of them'),
 ('I  Interface segregation','TokenPool, IdempotencyStore, InventoryUnitRepository, OrderObserver','No giant InventoryManager'),
 ('D  Dependency inversion','Services depend on TokenPool / PaymentGateway / LeaseManager','Redis swappable; DB fallback is just another TokenPool')],
 [2.6,6.0,3.53],rh=0.85,hdr=PU,size=13)
notes(s,'One concrete class per principle. The best example is DIP: ReservationService depends on the TokenPool interface, so the Redis pool, the salted hot-key pool and the DB fallback are interchangeable.',
 'Show where Open/Closed applies.','Adding Stripe or hot-key salting was a new class registered in a factory; ReservationService and PaymentService were not edited.')
s=base('Design patterns and why','LLD • Patterns',PU)
pats=[('Facade','CheckoutFacade','One entry for reserve → pay → order',CY),('Saga','CheckoutSaga','Compensate: void auth, release unit',CY),('Strategy','PricingStrategy, TokenPool','Swap pricing / admission policy',PU),('Factory + Adapter','PaymentProviderFactory','Razorpay ↔ Stripe without code change',AM),('Decorator','CircuitBreakerGateway','Breaker wraps any gateway',AM),('State','OrderState','Illegal transitions impossible',GR),('Observer','OrderEventPublisher','Notify, ship, analytics decoupled',GR),('Outbox','outbox_event','Event + data in one transaction',BL),('Repository','InventoryUnitRepository','SQL hidden behind interface',BL)]
for i,(nm,cl,why,c) in enumerate(pats):
    x=0.6+(i%3)*4.1; y=1.55+(i//3)*1.78
    rect(s,x,y,3.93,1.6,CARD); icon(s,x+0.2,y+0.25,0.62,nm[0],c,20)
    txt(s,x+1.0,y+0.15,2.85,0.4,nm,17,WHITE,True); txt(s,x+1.0,y+0.55,2.85,0.35,cl,11,c,True); txt(s,x+1.0,y+0.92,2.85,0.6,why,12,MUTED)
notes(s,'Nine patterns, each chosen for a specific failure: Saga for compensation, Factory plus Adapter for payment providers, Decorator for the circuit breaker, State for legal order transitions, Outbox for reliable events.',
 'Which pattern handles payment provider switching?','Factory + Adapter: PaymentProviderFactory returns a PaymentGateway; Razorpay/Stripe adapters implement it; the CircuitBreakerGateway decorator wraps either.')
s=base('Sequence: Buy Now → reservation','LLD • Sequence',PU); img(s,D3+'seq_reservation.png',0.6,1.5,12.13,5.35)
notes(s,'Buy Now: idempotency check, Redis token DECR, then one Postgres transaction claims a unit with SKIP LOCKED, inserts the reservation and the outbox event, and commits. Only then is the answer YES.',
 'Two users click for the last unit at the same instant?','Only one token remains in Redis; even if both got through, SKIP LOCKED gives them different rows or none, and UNIQUE stops a second unit per customer.')
s=base('Payment: authorize, then capture','LLD • Sequence',AM)
img(s,D3+'seq_payment.png',0.6,1.5,8.4,5.35)
card(s,9.2,1.5,3.53,1.68,'Idempotency-Key',['Duplicate → same stored answer, never a second charge.'],CY,12)
card(s,9.2,3.33,3.53,1.68,'Fencing version',['Payment after TTL expiry fails the version check → auth voided.'],AM,12)
card(s,9.2,5.16,3.53,1.69,'Failure = release',['Declined payment returns the unit to the pool for the next buyer.'],RD,12)
notes(s,'We authorize first and capture only after the order exists. If anything fails between, we void the authorization instead of refunding a captured charge.',
 'Payment succeeds but order creation fails?','The PaymentAuthorized event sits in the outbox; Order consumes it when back, deduped by the inbox. If it never completes, reconciliation voids the auth — the customer is never charged for nothing.')
s=base('State machines','LLD • State pattern',PU)
img(s,D3+'state_reservation.png',0.6,1.5,5.9,5.35); img(s,D3+'state_order.png',6.83,1.5,5.9,5.35)
notes(s,'Reservation: HELD → PAID or EXPIRED/RELEASED. Order: CREATED → CONFIRMED → SHIPPED → DELIVERED, with cancel and compensation branches. Transitions are guarded by version columns.',
 'What stops an expired reservation being paid?','The version (fencing) check: payment updates WHERE version = expected; the sweeper bumped it, so 0 rows update and the auth is voided.')

# 19 Divider Data & API
s=divider('03','Data, API & Events','22 tables • idempotent REST API • outbox + inbox',AM,'Student 3 — Data & API Engineer')
notes(s,'Section three: data, API and events.')
s=base('ER diagram — PostgreSQL, 22 tables','Data',AM); img(s,R+'04_Database/drawio/er_diagram.png',0.6,1.5,12.13,4.75)
x=0.6
for t,c in [('one row per unit',AM),('UNIQUE per customer',GR),('idempotency_record',CY),('outbox (same TX)',PU),('inbox + lease',RD)]:
    x+=chip(s,x,6.42,t,c,2.3)+0.157
notes(s,'22 tables in PostgreSQL. The key choice: inventory is one row per unit, not a counter, so buyers lock different rows. Constraints — CHECK, partial UNIQUE, idempotency_record — make illegal states unrepresentable.',
 'SQL or NoSQL and why?','SQL: we need multi-row ACID transactions (unit + reservation + outbox in one commit) and constraints as the last line of defence. ADR-004.')
s=base('API & idempotency','API • OpenAPI / Swagger',AM)
table(s,0.6,1.5,7.6,[('Method','Endpoint','Key responses'),('GET','/sales/{id}/stock-status','200 • CDN max-age=1'),('POST','/sales/{id}/reservations','201 • 200 replay • 409 • 503'),('POST','/checkout','200 • 409 expired'),('POST','/payments','202 • 402 • 503 breaker'),('POST','/payments/webhook','200 • 401 bad HMAC'),('GET','/orders/{id}','200 order + state'),('POST','/orders/{id}/cancel','202 • 409 shipped')],[1.0,3.6,3.0],rh=0.55,hdr=AM,size=12)
card(s,8.45,1.5,4.28,1.7,'Idempotency-Key header',['Same key → same stored response (200 replay). 2 replays in the sim, 0 double charges.'],CY,12)
card(s,8.45,3.35,4.28,1.55,'409 SOLD_OUT',['Also 409 ALREADY_RESERVED. Fast, cacheable NO — from L1, L2 or L3.'],RD,12)
card(s,8.45,5.05,4.28,1.8,'503 + Retry-After',['Waiting room under overload: tells clients when to come back instead of hammering us.'],AM,12)
notes(s,'Every write takes an Idempotency-Key. Reservations return 201 on success, 200 on replay, 409 for sold-out, and 503 with Retry-After when we shed load. The full spec is live on our Swagger page.',
 'How do you stop a duplicate order?','Idempotency-Key at the API, UNIQUE(sale, customer) in the DB, and the inbox table at the Order consumer — three independent layers.')
s=base('Events: transactional outbox + inbox','Events',AM)
steps=[('Service TX','write data + outbox row in ONE commit',CY),('Relay','polls outbox → publishes to Kafka',PU),('Kafka','durable, replayable log',BL),('Inbox','INSERT message_id; duplicate = skip',GR),('Consumer','Order / Shipment / Notification',AM)]
for i,(h,d,c) in enumerate(steps):
    x=0.6+i*2.5
    rect(s,x,1.7,2.15,2.2,CARD); rect(s,x,1.7,2.15,0.07,c,MSO_SHAPE.RECTANGLE); icon(s,x+0.75,1.95,0.65,str(i+1),c,18)
    txt(s,x+0.1,2.7,1.95,0.4,h,16,WHITE,True,PP_ALIGN.CENTER); txt(s,x+0.1,3.1,1.95,0.8,d,11,MUTED,align=PP_ALIGN.CENTER)
    if i<4: a=s.shapes.add_shape(MSO_SHAPE.RIGHT_ARROW,Inches(x+2.18),Inches(2.6),Inches(0.3),Inches(0.4)); a.fill.solid(); a.fill.fore_color.rgb=MUTED; a.line.fill.background()
stat(s,0.6,4.3,3.9,2.45,'0','events lost — outbox commits with the data',PU,48,14)
stat(s,4.72,4.3,3.9,2.45,'0','duplicate orders with inbox (13 without)',GR,48,14)
stat(s,8.83,4.3,3.9,2.45,'Watermark','event time vs processing time → late events reconciled',AM,34,14)
notes(s,'The outbox guarantees we never lose an event: it commits with the business data. The inbox guarantees we never process one twice. Together that is effectively-once delivery.',
 'What if the payment webhook arrives late?','We order by event time with a watermark; late events go to reconciliation, which voids or captures based on the reservation\'s current state.')

# 23 Divider Reliability
s=divider('04','Concurrency & Reliability','SKIP LOCKED • 14 failure modes • resilience controls • proof',GR,'Student 4 — Reliability Engineer')
notes(s,'Section four: concurrency, failure handling and our proof.')
s=base('Concurrency: no oversell, by construction','Reliability • Inventory',GR)
img(s,D3+'concurrency_flow.png',0.6,1.5,6.2,5.35)
rect(s,7.05,1.5,5.68,1.5,CARD)
txt(s,7.25,1.58,5.3,1.4,['SELECT id FROM inventory_unit','WHERE sale_id=$1 AND status=\'AVAILABLE\'','LIMIT 1 FOR UPDATE SKIP LOCKED;'],13,CY,font='Consolas',sp=2)
card(s,7.05,3.15,5.68,1.15,'Write skew prevented',['Each buyer locks a different row — no read-then-write race.'],GR,12)
card(s,7.05,4.42,5.68,1.15,'No hot-row queue',['SKIP LOCKED: parallel claims, nobody waits on a lock.'],AM,12)
card(s,7.05,5.69,5.68,1.16,'DB is the last line',['CHECK(status) + partial UNIQUE(sale, customer).'],PU,12)
notes(s,'Oversell is a write-skew problem. We remove the shared counter: each unit is a row, buyers claim with FOR UPDATE SKIP LOCKED, so they never wait on each other and never claim the same unit.',
 'Optimistic or pessimistic locking?','Pessimistic SKIP LOCKED for stock (high contention, retries would storm); optimistic version columns for everything else (low contention). ADR-008.')
s=base('14 production failure modes we designed for','Reliability',GR)
fm=[('Metastable failure','Load shedder + admission + retry budget',RD),('Retry storm','Idempotent-only retries, jitter, 10% budget',RD),('Tail latency','Hedged reads at p95 (reads only)',AM),('Cache stampede','Singleflight + TTL jitter',AM),('Hot key (the SKU)','16 salted Redis sub-pools',AM),('Duplicate delivery','Outbox + inbox = effectively-once',PU),('Split-brain leader','Lease + fencing token checked by Postgres',PU),('Gray failure','Real-traffic health, phi-accrual',CY),('Unbalanced backends','Power of two choices (in-flight)',CY),('Capacity guesswork',"Little's law, pool 40, <70% util",BL),('Write skew (oversell)','Unit rows + SKIP LOCKED + UNIQUE',GR),('Late events','Event time + watermark → reconcile',GR),('Blast radius','Flash sale in its own cell',BL),('Coordinated omission','Open-loop load tests',BL)]
for i,(f,c,col_) in enumerate(fm):
    cx=0.6+(i//7)*6.15; cy=1.5+(i%7)*0.75
    rect(s,cx,cy,5.98,0.66,CARD)
    rect(s,cx,cy,0.55,0.66,col_,adj=0.15); txt(s,cx,cy,0.55,0.66,str(i+1),15,BG,True,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE)
    txt(s,cx+0.7,cy+0.03,2.35,0.6,f,14,WHITE,True,anchor=MSO_ANCHOR.MIDDLE)
    txt(s,cx+3.05,cy+0.03,2.9,0.6,c,11,MUTED,anchor=MSO_ANCHOR.MIDDLE)
txt(s,0.6,6.8-0.12,12.13,0.3,'"We would rather reject 5% of requests than let retries turn a blip into a 40-minute outage."',12,AM,True,PP_ALIGN.CENTER)
notes(s,'Fourteen real production failure modes, each with a named control. Six of them we actually simulated — next slides show the numbers.',
 'What is a metastable failure?','A state where the system stays overloaded even after the trigger goes away, usually because retries keep load high. Retry budgets + load shedding break the loop.')
s=base('Resilience controls on the request path','Reliability',GR)
img(s,D2+'resilience_controls.png',0.6,1.5,8.4,5.35)
for i,(t,c) in enumerate([('Load shedder → 503 + Retry-After',RD),('Retry budget 10% + full jitter',RD),('Circuit breaker (Decorator)',AM),('Singleflight cache',AM),('16 salted token pools',PU),('Lease + fencing token',PU),('P2C load balancing',CY),('Phi-accrual outlier ejection',CY),('Inbox dedupe',GR)]):
    chip(s,9.2,1.55+i*0.59,t,c,3.53,11)
notes(s,'This diagram shows where each control sits on the request path — shedding at the edge, retry budgets in clients, breakers around the gateway, fencing tokens at the database.',
 'Why not retry everything?','Retries multiply load exactly when the system is weakest. We retry only idempotent calls, with jitter, within a 10% budget.')

# 27 Proof charts
s=base('Proof: simulation of the exact test case','Validation • 11_AI_Assisted_Validation',GR)
for i,(nu,l,c) in enumerate([('10,200','requests incl. duplicates',CY),('107','reached Postgres',AM),('100','sold — exactly',GR),('415 / 0','invariant checks / violations',PU)]):
    stat(s,0.6+i*3.08,1.5,2.9,1.3,nu,l,c,30,12)
bar(s,0.6,2.95,6.6,3.95,['L1 CDN','L2 in-proc','L3 rejected','L3 replay','L4 Postgres'],[('Requests answered',(9921,163,7,2,107))],[CY,TE,PU,BL,AM],title='Where 10,200 requests were answered',size=11)
bar(s,7.4,2.95,5.33,3.95,['Naive','SALESTORM'],[('Units sold',(650,100))],[RD,GR],title='Units sold (stock 100)',size=11)
notes(s,'Our simulator replayed the full test case: 10,200 requests including duplicates. 97% were answered at the CDN, 107 reached Postgres, exactly 100 sold, and 415 invariant checks found zero violations. Same load on a naive counter sold 650.',
 'Is a simulation enough proof?','It proves the logic and invariants; the Postgres checks (22 tables, constraints passed) prove the DB layer; Locust/JMeter open-loop scripts in the repo test throughput.')
s=base('Proof: resilience experiments','Validation • resilience_sim.py',GR)
bar(s,0.6,1.5,4.0,2.65,['Naive','Budgeted'],[('Load ×',(4.26,1.01))],[RD,GR],title='Retry storm: load after 2 s blip',fmt='0.00"×"',size=10)
bar(s,4.67,1.5,4.0,2.65,['No inbox','With inbox'],[('Dupes',(13,0))],[RD,GR],title='30 s outage: duplicate orders',size=10)
bar(s,8.73,1.5,4.0,2.65,['Redis lock only','+ fencing'],[('Lost',(3,0))],[RD,GR],title='Stale lock: buyers lost unit',size=10)
for i,(nu,l,c) in enumerate([('97.2%','goodput, recovered < 1 s (naive never recovered)',GR),('2,000 → 1','cache misses → DB reads (singleflight)',AM),('57','max ops on one key (16 salted pools, 10k buyers)',PU),('1 → 1,902 ms','p99 closed-loop (lies) vs open-loop (truth)',RD)]):
    stat(s,0.6+i*3.08,4.4,2.9,2.45,nu,l,c,28,12)
notes(s,'Six resilience experiments. Retry budgets keep load at 1.01x instead of 4.26x; the inbox removes all 13 duplicates; fencing tokens save 3 buyers; singleflight turns 2,000 misses into one DB read; salting caps a hot key at 57 ops; and open-loop testing reveals the true 1.9 s p99 that closed-loop hid.',
 'What is coordinated omission?','A closed-loop load tester stops sending while the server stalls, so it never records the slow requests. Open-loop measures from intended start time: p99 1,902 ms, not 1 ms.')

# 28 Outage timeline
s=base('30 s Order Service outage — recovery timeline','Reliability • Recovery',GR)
rect(s,0.9,3.3,11.5,0.08,CARD2,MSO_SHAPE.RECTANGLE); rect(s,3.2,3.22,4.6,0.24,RD,adj=0.5)
txt(s,3.2,2.75,4.6,0.4,'Order Service DOWN (30 s)',13,RD,True,PP_ALIGN.CENTER)
ev=[('t = 0 s','Sale live; orders flowing',GR,1.0),('t = 5 s','Order crashes; reservations + payments continue',RD,3.2),('t = 5–35 s','Events accumulate in outbox / Kafka',AM,5.5),('t = 35 s','Order restarts, replays from offset',CY,7.8),('t < 36 s','Inbox drops redeliveries → 0 duplicates',GR,10.0)]
for t,d,c,x in ev:
    icon(s,x+0.55,3.08,0.5,'●',c,12)
    txt(s,x-0.2,1.7,2.0,0.4,t,16,c,True,PP_ALIGN.CENTER)
    rect(s,x-0.2,3.9,2.0,1.5,CARD); txt(s,x-0.1,3.97,1.8,1.4,d,12,WHITE,align=PP_ALIGN.CENTER)
for i,(nu,l,c) in enumerate([('0','paid orders lost',GR),('0','duplicate orders (13 without inbox)',PU),('0 s','sync path down: reserve + pay kept running',CY)]):
    stat(s,0.6+i*4.1,5.65,3.93,1.2,nu,l,c,30,12)
notes(s,'During the outage, buyers keep reserving and paying because the order step is asynchronous. Events wait in the outbox and Kafka; when Order restarts it replays, and the inbox discards redeliveries. Nothing lost, nothing duplicated.',
 'Order Service is down for 30 seconds, what happens?','Exactly this timeline: sync path unaffected, async backlog drained on restart, inbox dedupe, reconciliation voids any auth whose order never materialises.')

# 29 ADRs
s=base('Architecture decision records (10)','Decisions • 10_ADR',BL)
adrs=[('001','Cache-Hit Ladder for latency and load',CY),('002','Inventory as unit rows + SKIP LOCKED',GR),('003','Redis token pool as admission control',PU),('004','PostgreSQL (SQL) over NoSQL for money & stock',AM),('005','Sync reserve/authorize, async order/ship/notify',BL),('006','Authorize-then-capture payments',AM),('007','Transactional outbox + orchestrated saga',PU),('008','Pessimistic for stock, optimistic elsewhere',GR),('009','Shedding, retry budget, fencing, inbox',RD),('010','Own cell + open-loop load testing',CY)]
for i,(k,t,c) in enumerate(adrs):
    cx=0.6+(i//5)*6.15; cy=1.55+(i%5)*1.04
    rect(s,cx,cy,5.98,0.88,CARD); rect(s,cx,cy,1.25,0.88,c,adj=0.15)
    txt(s,cx,cy,1.25,0.88,'ADR '+k,14,BG,True,PP_ALIGN.CENTER,MSO_ANCHOR.MIDDLE)
    txt(s,cx+1.4,cy,4.5,0.88,t,15,WHITE,True,anchor=MSO_ANCHOR.MIDDLE)
notes(s,'Ten ADRs record every major trade-off with alternatives considered and consequences. Each team member owns specific ADRs.',
 'Sync or async — how did you decide?','Anything the buyer must see immediately (reserve, authorize) is sync; everything that can wait (order, shipment, notification) is async via outbox, so its outage cannot block a sale. ADR-005.')

# 30 Tools
s=base('Tools we used','Tooling • 13_Tools_Guide.md',BL)
tools=[('Draw.io','HLD, LLD, ER diagrams',CY),('StarUML / UML','class, sequence, state',PU),('MySQL Workbench','ER from schema_mysql.sql',BL),('dbdiagram.io','salestorm.dbml ER',TE),('Swagger / OpenAPI','live API docs',GR),('Postman','collection + idempotency tests',AM),('Locust','open-loop load tests',RD),('JMeter','throughput test plan',RD),('GitHub','repo, PRs, history',WHITE),('GitHub Pages','live documentation site',CY)]
for i,(nm,d,c) in enumerate(tools):
    x=0.6+(i%5)*2.45; y=1.6+(i//5)*2.6
    rect(s,x,y,2.27,2.35,CARD); icon(s,x+0.79,y+0.25,0.7,nm[0],c,22)
    txt(s,x+0.08,y+1.08,2.11,0.5,nm,15,WHITE,True,PP_ALIGN.CENTER); txt(s,x+0.08,y+1.55,2.11,0.7,d,11,MUTED,align=PP_ALIGN.CENTER)
notes(s,'Every artifact was built with an industry tool: Draw.io and UML for diagrams, Workbench and dbdiagram for the schema, Swagger and Postman for the API, Locust and JMeter for load, GitHub Pages for the live site.',
 'Can you show the API live?','Yes — the Swagger page on GitHub Pages renders our openapi.yaml with every endpoint and error code.')

# 31 Team
s=base('Team ownership — everyone can answer anything','Team • TEAM_OWNERSHIP.md',BL)
team=[('S1','System Architect','HLD, scalability, deployment, cell','ADR 001 • 003 • 004 • 005 • 010',CY),('S2','LLD & Design Engineer','Classes, SOLID, patterns, sequences, states','UML • 06_SOLID • 07_Patterns',PU),('S3','Data & API Engineer','22 tables, OpenAPI, outbox/inbox, payments','ADR 004 • 006 • 007',AM),('S4','Reliability Engineer','Concurrency, 14 failure modes, security, proof','ADR 002 • 008 • 009',GR)]
for i,(k,r,d,a,c) in enumerate(team):
    x=0.6+i*3.08
    rect(s,x,1.6,2.9,5.2,CARD); rect(s,x,1.6,2.9,0.08,c,MSO_SHAPE.RECTANGLE)
    icon(s,x+0.95,1.95,1.0,k,c,24)
    txt(s,x+0.1,3.1,2.7,0.8,r,17,WHITE,True,PP_ALIGN.CENTER)
    txt(s,x+0.15,3.95,2.6,1.3,d,13,MUTED,align=PP_ALIGN.CENTER)
    chip(s,x+0.15,5.6,a,c,2.6,10)
notes(s,'Four owners, but everyone has walked through every module, so any of us can take any question.',
 'Who designed the concurrency model?','Student 4 owns it, but every member can explain SKIP LOCKED, the token pool and the UNIQUE constraint.')

# 32 Closing
s=base()
qp='/tmp/salestorm_qr.png'
q=qrcode.QRCode(border=2,box_size=10); q.add_data(LIVE); q.make(fit=True); q.make_image(fill_color='black',back_color='white').save(qp)
rect(s,-1.5,4.5,7,7,CARD2,MSO_SHAPE.OVAL)
txt(s,0.8,1.0,8,0.4,'LIVE DEMO • DOCS • CODE',14,CY,True)
txt(s,0.8,1.45,8,1.2,'Thank you',64,WHITE,True)
txt(s,0.8,2.75,8.3,0.6,TAG(MUTED),22)
txt(s,0.8,3.65,8.3,0.4,'Live site',12,MUTED,True); txt(s,0.8,3.95,8.3,0.45,LIVE,15,CY,True)
txt(s,0.8,4.45,8.3,0.4,'Swagger API',12,MUTED,True); txt(s,0.8,4.75,8.3,0.45,LIVE+'api.html',15,CY,True)
txt(s,0.8,5.25,8.3,0.4,'Repository',12,MUTED,True); txt(s,0.8,5.55,8.3,0.45,REPO,15,CY,True)
txt(s,0.8,6.2,6,0.6,'Questions?',28,AM,True)
rect(s,9.35,1.6,3.4,3.9,WHITE,adj=0.05); img(s,qp,9.5,1.75,3.1,3.1,card=False,pad=0)
txt(s,9.35,4.9,3.4,0.5,'Scan for the live site',13,BG,True,PP_ALIGN.CENTER)
txt(s,9.35,5.7,3.4,0.9,['100 sold • 0 oversold','0 double charges • 0 lost orders'],13,GR,True,PP_ALIGN.CENTER,sp=2)
notes(s,'Scan the QR for our live site with every diagram, the Swagger API and the simulation results. Caches can say NO; only the database can say YES. Thank you.',
 'What would you build next?','Multi-region active-passive for the cell, real gateway sandbox integration, and chaos tests in CI using the same resilience simulator.')

out=R+'12_Presentation/SALESTORM_Final_Presentation.pptx'
p.save(out); print('slides',n,out)

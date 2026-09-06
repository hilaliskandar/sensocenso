import os, hashlib
import fitz
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle, Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT='/mnt/data'
vals=[
 ('A01','Área 001','3509007001',47,15622,5464,1554,560),
 ('A02','Área 002','3509007002',25,9159,3130,1532,514),
 ('A03','Área 003','3509007003',31,15713,5562,1518,539),
 ('A04','Área 004','3509007004',28,11857,4312,1080,403),
 ('A05','Área 005','3509007005',38,23161,7801,2339,787),
 ('A06','Área 006','3509007006',27,15538,5360,1652,564),
 ('A07','Área 007','3509007007',11,3982,1318,1509,490),
]
pt=sum(r[4] for r in vals); dt=sum(r[5] for r in vals); np=sum(r[6] for r in vals); nd=sum(r[7] for r in vals); st=sum(r[3] for r in vals)
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'; FONTB='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
pdfmetrics.registerFont(TTFont('DejaVu',FONT)); pdfmetrics.registerFont(TTFont('DejaVuB',FONTB))
PAGE=landscape(A4); W,H=PAGE

def fmt_int(x): return f'{int(x):,}'.replace(',','.')
def fmt_pct(x): return f'{x:.2f}'.replace('.',',')+'%'

def make_ref_page(path, volume):
    c=canvas.Canvas(path,pagesize=PAGE)
    c.setFont('DejaVuB',15)
    c.drawString(28,H-48,'2. Diretório e referência populacional, domiciliar e amostral das Áreas de Ponderação')
    c.setFont('DejaVu',7.2); c.setFillColor(colors.HexColor('#555555'))
    c.drawString(28,H-66,'Estimativas ponderadas dos microdados da Amostra e bases amostrais não ponderadas; os percentuais expressam a participação de cada APOND no total municipal estimado.')
    c.setFillColor(colors.black)
    phead=ParagraphStyle('h',fontName='DejaVuB',fontSize=5.6,leading=6.4,alignment=1,textColor=colors.black)
    pcell=ParagraphStyle('c',fontName='DejaVu',fontSize=6.0,leading=6.8,alignment=1,textColor=colors.black)
    pleft=ParagraphStyle('l',fontName='DejaVu',fontSize=6.0,leading=6.8,alignment=0,textColor=colors.black)
    headers=['Rótulo','Nome editorial','Código APOND','Setores','População<br/>estimada','% da população<br/>estimada','Domicílios<br/>estimados','% dos domicílios<br/>estimados','Base amostral<br/>pessoas (n)','Base amostral<br/>domicílios (n)']
    data=[[Paragraph(h,phead) for h in headers]]
    for r in vals:
        a,nm,code,seto,pop,dom,npp,ndd=r
        row=[Paragraph(a,pcell),Paragraph(nm,pleft),Paragraph(code,pcell),Paragraph(str(seto),pcell),Paragraph(fmt_int(pop),pcell),Paragraph(fmt_pct(pop/pt*100),pcell),Paragraph(fmt_int(dom),pcell),Paragraph(fmt_pct(dom/dt*100),pcell),Paragraph(fmt_int(npp),pcell),Paragraph(fmt_int(ndd),pcell)]
        data.append(row)
    data.append([Paragraph('Total',phead),Paragraph('Caieiras',phead),Paragraph('—',phead),Paragraph(str(st),phead),Paragraph(fmt_int(pt),phead),Paragraph('100,00%',phead),Paragraph(fmt_int(dt),phead),Paragraph('100,00%',phead),Paragraph(fmt_int(np),phead),Paragraph(fmt_int(nd),phead)])
    widths=[38,72,88,43,66,72,68,76,76,80]
    t=Table(data,colWidths=widths,repeatRows=1,hAlign='LEFT')
    style=[
      ('VALIGN',(0,0),(-1,-1),'MIDDLE'),('TOPPADDING',(0,0),(-1,-1),3),('BOTTOMPADDING',(0,0),(-1,-1),3),
      ('LINEABOVE',(0,0),(-1,0),.75,colors.black),('LINEBELOW',(0,0),(-1,0),.75,colors.black),
      ('LINEABOVE',(0,-1),(-1,-1),.5,colors.HexColor('#777777')),('LINEBELOW',(0,-1),(-1,-1),.75,colors.black),
      ('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#f2f2f2')),
      ('ALIGN',(3,1),(-1,-1),'RIGHT'),('ALIGN',(0,0),(0,-1),'CENTER'),('ALIGN',(2,0),(2,-1),'CENTER')
    ]
    t.setStyle(TableStyle(style))
    tw,th=t.wrap(sum(widths),300)
    t.drawOn(c,28,H-86-th)
    y=H-100-th
    c.setFillColor(colors.HexColor('#444444'))
    c.setFont('DejaVuB',7.0); c.drawString(28,y,'Como ler as grandezas')
    c.setFont('DejaVu',6.7)
    notes=[
      '• População estimada: soma dos pesos calibrados dos registros de pessoas pertencentes à APOND; não corresponde a uma contagem simples da amostra.',
      '• Domicílios estimados: soma dos pesos calibrados dos registros domiciliares pertencentes à APOND.',
      '• Percentual estimado: estimativa da APOND dividida pela estimativa municipal correspondente × 100.',
      '• Base amostral (n): número de registros efetivamente observados na amostra, antes da ponderação. Por isso n não deve ser interpretado como população ou domicílios estimados.',
      '• As estimativas e percentuais utilizam os pesos calibrados correspondentes ao universo analítico; os valores exibidos são arredondados apenas para apresentação.'
    ]
    yy=y-14
    for note in notes:
        c.drawString(34,yy,note); yy-=11
    c.setFont('DejaVu',6.4); c.setFillColor(colors.HexColor('#666666'))
    c.drawString(28,14,f'TIC-TIM - Censo Demográfico 2022 - Caieiras - Caderno tabular e cartográfico por APOND - Volume {volume}')
    c.drawRightString(W-28,14,'Página 4')
    c.save()

def replace_page(src,out,volume):
    ref=f'/mnt/data/ref_page_v{volume}.pdf'; make_ref_page(ref,volume)
    d=fitz.open(src); r=fitz.open(ref)
    p0=d[0]
    rect=fitz.Rect(p0.rect.width-110,p0.rect.height-30,p0.rect.width-18,p0.rect.height-7)
    p0.draw_rect(rect,color=(31/255,52/255,72/255),fill=(31/255,52/255,72/255),overlay=True)
    d.delete_page(3); d.insert_pdf(r,from_page=0,to_page=0,start_at=3)
    d.save(out,garbage=4,deflate=True)
    d.close(); r.close()

files={
  'I':'/mnt/data/caieiras_volume1_v1/TIC_TIM_Censo2022_Caieiras_Caderno_Tabular_Cartografico_Vol1_v1.pdf',
  'II':'/mnt/data/caieiras_volume2_v1/TIC_TIM_Censo2022_Caieiras_Caderno_Tabular_Cartografico_Vol2_v1.pdf',
  'III':'/mnt/data/caieiras_volume3_v1/TIC_TIM_Censo2022_Caieiras_Caderno_Tabular_Cartografico_Vol3_v1.pdf',
}
outdir='/mnt/data/caieiras_revisao_referencia'; os.makedirs(outdir,exist_ok=True)
outs=[]
for vol,src in files.items():
    out=os.path.join(outdir,os.path.basename(src).replace('_v1.pdf','_v2_REFERENCIA.pdf'))
    replace_page(src,out,vol); outs.append((vol,out))
cons=os.path.join(outdir,'TIC_TIM_Censo2022_Caieiras_Caderno_Tabular_Cartografico_Consolidado_v2_REFERENCIA.pdf')
dc=fitz.open()
for _,p in outs:
    x=fitz.open(p); dc.insert_pdf(x); x.close()
dc.save(cons,garbage=4,deflate=True); dc.close()
for vol,p in outs+[('CONS',cons)]:
    h=hashlib.sha256(open(p,'rb').read()).hexdigest(); doc=fitz.open(p)
    print(vol,os.path.basename(p),doc.page_count,os.path.getsize(p),h); doc.close()


import re, zipfile
from datetime import date
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.text import slugify
from audit.services import record_event
from music.models import Release, ReleaseTrack, Track, MusicCredit
from music.services import add_release_track, create_credit, create_release, create_track
from rights.models import RightsParty, TrackWork, Work, WorkContributor, MasterRight, PublishingRight
from rights.services import add_contributor, add_master_right, add_publishing_right, create_party, create_work, link_track

M="http://schemas.openxmlformats.org/spreadsheetml/2006/main"
R="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
def txt(v): return " ".join(str(v or "").replace("\n"," ").split()).strip()
def col(n):
    out=""
    while n: n,r=divmod(n-1,26); out=chr(65+r)+out
    return out
def split(v): return [x.strip() for x in re.split(r"[,;|/\n]+",txt(v)) if x.strip()]
def pct(v):
    try:
        n=Decimal(txt(v).replace("%",""))
        return n*100 if n<=1 else n
    except (InvalidOperation,ValueError): return None
def dur(v):
    p=txt(v).split(":")
    try: return int(p[0])*60+int(float(p[1])) if len(p)==2 else int(float(p[0]))
    except (ValueError,IndexError): return None
def workbook(upload):
    with zipfile.ZipFile(upload) as z:
        shared=[]
        if "xl/sharedStrings.xml" in z.namelist():
            root=ET.fromstring(z.read("xl/sharedStrings.xml"))
            for x in root.findall(".//{%s}si"%M): shared.append(txt("".join(t.text or "" for t in x.iter("{%s}t"%M))))
        wb=ET.fromstring(z.read("xl/workbook.xml")); rel=ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets={x.attrib["Id"]:x.attrib["Target"] for x in rel}
        result={}
        for sh in wb.findall(".//{%s}sheet"%M):
            name=sh.attrib["name"].strip()
            target=targets[sh.attrib["{%s}id"%R]]
            path=target if target.startswith("xl/") else "xl/"+target.lstrip("/")
            root=ET.fromstring(z.read(path)); rows=[]
            for row in root.findall(".//{%s}sheetData/{%s}row"%(M,M)):
                vals={}
                for cell in row.findall("{%s}c"%M):
                    ref=cell.attrib.get("r",""); letters=re.sub(r"\d","",ref)
                    v=cell.find("{%s}v"%M)
                    value=v.text if v is not None else ""
                    if cell.attrib.get("t")=="s" and value: value=shared[int(value)]
                    if cell.attrib.get("t")=="inlineStr": value=txt("".join(t.text or "" for t in cell.iter("{%s}t"%M)))
                    vals[letters]=value
                if vals:
                    highest=max([sum((ord(ch)-64)*26**i for i,ch in enumerate(reversed(k))) for k in vals] or [0])
                    rows.append([vals.get(col(i),"") for i in range(1,highest+1)])
            result[name]=rows
        return result
def rows(sheet, header):
    if len(sheet)<header: return []
    heads=[txt(x).lower() for x in sheet[header-1]]
    return [dict(zip(heads,r)) for r in sheet[header:] if any(txt(x) for x in r)]
def _key(value): return re.sub(r"[^a-z0-9]+", " ", str(value or "").lower()).strip()
def get(row,*names):
    normalized={_key(key): value for key,value in row.items()}
    for name in names:
        if txt(normalized.get(_key(name))): return txt(normalized[_key(name)])
    return ""
def _inline_split_rows(row):
    result=[]
    for key,value in row.items():
        label=_key(key)
        if not txt(value) or not re.search(r"\b(writer|songwriter|composer|producer|publisher)\b",label) or any(x in label for x in ("split","share","%")): continue
        role="publisher" if "publisher" in label else "producer" if "producer" in label else "songwriter"
        stem=label.replace("name","").strip(); share=""
        for share_key,share_value in row.items():
            normalized=_key(share_key)
            if stem and stem in normalized and any(x in normalized for x in ("split","share","%")): share=share_value; break
        result.append({"title":get(row,"title","track title","track name","song title","song"),"contributor name":value,"role":role,"split %":share})
    return result


def credit_role(role):
    value=role.lower()
    if "featured" in value: return "featured_artist"
    if "producer" in value: return "producer"
    if "composer" in value: return "composer"
    if "writer" in value or "lyric" in value: return "songwriter"
    if "artist" in value or "performer" in value: return "primary_artist"
    return "other"

def party_type(role):
    r=role.lower()
    return RightsParty.Type.PUBLISHER if "publisher" in r else RightsParty.Type.PRODUCER if "producer" in r else RightsParty.Type.ARTIST if "artist" in r or "performer" in r else RightsParty.Type.SONGWRITER if any(x in r for x in ("writer","lyric","composer")) else RightsParty.Type.OTHER
@transaction.atomic
def _import_release_sheets(*,actor,organization,artist,sheets,title="Ts & Cs Apply",release_date=date(2026,9,1),request=None):
    master=next((v for k,v in sheets.items() if k.lower().startswith("master tracklist")), next(iter(sheets.values()), []))
    split_rows=rows(next((v for k,v in sheets.items() if "royalty" in k.lower() and "split" in k.lower()), []),1)
    credit_rows=rows(next((v for k,v in sheets.items() if "credit" in k.lower() and "contributor" in k.lower()), []),1)
    mix_rows=rows(next((v for k,v in sheets.items() if k.lower().startswith("mixing & mastering")),[]),3)
    tracks=rows(master,2)
    if not tracks: raise ValidationError("The workbook contains no Master Tracklist New rows.")
    release=Release.objects.filter(organization=organization,primary_artist=artist,title__iexact=title).first()
    if not release:
        upc=re.sub(r"\D","",get(tracks[0],"upc"))[:14]
        release=create_release(actor=actor,organization=organization,data={"primary_artist":artist,"title":title,"slug":slugify(title),"release_type":Release.Type.ALBUM if len(tracks)>1 else Release.Type.SINGLE,"status":Release.Status.RELEASED,"planned_release_date":release_date,"original_release_date":release_date,"upc_ean":upc,"internal_notes":"Imported from the Ts & Cs Apply release workbook."},request=request)
    imported=0
    for number,row in enumerate(tracks,1):
        title_value=get(row,"title","track title","track name","song title","song")
        if not title_value: continue
        source_track_number=get(row,"track #","track number","track no")
        try: track_number=int(float(source_track_number))
        except (TypeError,ValueError): track_number=number
        raw_isrc=get(row,"isrc"); isrc=re.sub(r"[^A-Za-z0-9]","",raw_isrc).upper()
        if not re.fullmatch(r"[A-Z]{2}[A-Z0-9]{3}\d{7}", isrc):
            isrc=""
        track=Track.objects.filter(organization=organization,primary_artist=artist,**({"isrc":isrc} if isrc else {"title__iexact":title_value})).first()
        mix=next((x for x in mix_rows if get(x,"title").lower()==title_value.lower()),{})
        notes="; ".join(filter(None,[get(row,"progress notes"),get(row,"mix comments"),"Beat stems: "+get(row,"beat stems") if get(row,"beat stems") else "","Vocal stems: "+get(row,"vocal stems") if get(row,"vocal stems") else "","Mix status: "+(get(mix,"mix status") or get(row,"mix status"))]))
        if not track:
            track=create_track(actor=actor,organization=organization,data={"primary_artist":artist,"title":title_value,"slug":slugify(title_value),"isrc":isrc,"duration_seconds":dur(get(row,"duration")),"internal_notes":notes},request=request)
        if not ReleaseTrack.objects.filter(release=release,track=track).exists(): add_release_track(actor=actor,release=release,track=track,data={"track_number":track_number,"sequence":track_number},request=request)
        for name,role,order in [(x,"featured_artist",2) for x in split(get(row,"featured artists"))]+[(x,"producer",3) for x in split(get(row,"producers + full names"))]+[(x,"songwriter",4) for x in split(get(row,"writers"))]:
            if not MusicCredit.objects.filter(track=track,name__iexact=name,credit_role=role).exists(): create_credit(actor=actor,organization=organization,resource=track,data={"track":track,"name":name,"credit_role":role,"display_order":order},request=request)
        work=Work.objects.filter(organization=organization,title__iexact=title_value).first() or create_work(actor=actor,organization=organization,data={"title":title_value,"internal_reference":isrc},request=request)
        if not TrackWork.objects.filter(track=track,work=work).exists(): link_track(actor=actor,work=work,track=track,relationship_type=TrackWork.Relationship.PRIMARY,request=request)
        matching_split_rows=[]
        for item in split_rows:
            item_title=get(item,"title","track title","track name","song title","song")
            item_number=get(item,"track #","track number","track no")
            if (item_title and item_title.casefold()==title_value.casefold()) or (item_number and item_number==source_track_number):
                matching_split_rows.append(item)
        for item in matching_split_rows + _inline_split_rows(row):
            government_name=get(item,"government name")
            name=government_name or get(item,"contributor name","contributor","name","writer","songwriter","publisher")
            if not name or name.strip().upper() in {"TOTAL", "TOTALS"}: continue
            role_text=get(item,"role")
            external_identifier=(get(item,"ip name number") or get(item,"id number"))[:120]
            source_contributor=get(item,"contributor name","contributor","name","writer","songwriter","publisher")
            party=RightsParty.objects.filter(organization=organization,display_name__iexact=name).first()
            if not party and source_contributor:
                party=RightsParty.objects.filter(organization=organization,display_name__iexact=source_contributor).first()
            if not party and external_identifier:
                party=RightsParty.objects.filter(organization=organization,external_identifier=external_identifier).first()
            party_notes="; ".join(filter(None,[get(item,"associated society"),get(item,"address"),"Source contributor: "+source_contributor if source_contributor else "",get(item,"publisher")]))
            if party:
                party.display_name=name
                party.party_type=party_type(role_text)
                party.email=get(item,"email address") if "@" in get(item,"email address") else party.email
                party.external_identifier=external_identifier or party.external_identifier
                party.notes=party_notes or party.notes
                party.save(update_fields=("display_name","party_type","email","external_identifier","notes","updated_at"))
            else:
                party=create_party(actor=actor,organization=organization,data={"party_type":party_type(role_text),"display_name":name,"email":get(item,"email address") if "@" in get(item,"email address") else "","external_identifier":external_identifier,"notes":party_notes},request=request)
            share=pct(get(item,"split %","split percentage","writer split","publishing split","share","share %","ownership %"))
            writer_role=credit_role(role_text)
            rights_role=writer_role if writer_role in {"songwriter","composer"} else "other"
            if share:
                contributor=WorkContributor.objects.filter(work=work,party=party).first()
                if contributor:
                    contributor.role=rights_role; contributor.share_percentage=share; contributor.sequence=track_number; contributor.save(update_fields=("role","share_percentage","sequence","updated_at"))
                else:
                    try:
                        add_contributor(actor=actor,work=work,data={"party":party,"role":rights_role,"share_percentage":share,"sequence":track_number},request=request)
                    except ValidationError:
                        pass
            if not MusicCredit.objects.filter(track=track,name__iexact=name,credit_role=writer_role).exists(): create_credit(actor=actor,organization=organization,resource=track,data={"track":track,"name":name,"credit_role":writer_role,"display_order":track_number},request=request)
            master_share=pct(get(item,"master share (split)","master split","master share","master %"))
            if master_share and not MasterRight.objects.filter(track=track,party=party,territory_code="WORLDWIDE").exists(): add_master_right(actor=actor,track=track,data={"party":party,"ownership_percentage":master_share,"territory_code":"WORLDWIDE","notes":"Imported from Master Share (Split)."},request=request)
            publisher=get(item,"publisher")
            if publisher:
                pp=RightsParty.objects.filter(organization=organization,display_name__iexact=publisher).first() or create_party(actor=actor,organization=organization,data={"party_type":RightsParty.Type.PUBLISHER,"display_name":publisher,"notes":"Publisher from Royalty Split Sheets."},request=request)
                if share and not PublishingRight.objects.filter(work=work,party=pp,right_type=PublishingRight.Type.PUBLISHER,territory_code="WORLDWIDE").exists(): add_publishing_right(actor=actor,work=work,data={"party":pp,"right_type":PublishingRight.Type.PUBLISHER,"ownership_percentage":share,"territory_code":"WORLDWIDE"},request=request)
        imported+=1
    for item in credit_rows:
        name=get(item,"name")
        if name and not MusicCredit.objects.filter(release=release,name__iexact=name).exists():
            r=get(item,"role").lower(); role="executive_producer" if "executive" in r else "producer" if "producer" in r else "primary_artist" if "artist" in r else "other"
            create_credit(actor=actor,organization=organization,resource=release,data={"release":release,"name":name,"credit_role":role,"display_order":1},request=request)
    record_event(actor=actor,organization=organization,action="release.workbook_imported",resource=release,description=f"Imported release workbook for {release.title}.",request=request)
    return release,imported


def import_release_workbook(*,actor,organization,artist,upload,title="Ts & Cs Apply",release_date=date(2026,9,1),request=None):
    return _import_release_sheets(actor=actor, organization=organization, artist=artist, sheets=workbook(upload), title=title, release_date=release_date, request=request)

def import_release_tracker(*,actor,organization,artist,headers,values,title="Ts & Cs Apply",release_date=date(2026,9,1),additional_sheets=None,request=None):
    sheet=[[], list(headers)] + [list(row) for row in values]
    track_rows=rows(sheet,2)
    first=track_rows[0] if track_rows else {}
    tracker_title=get(first,"release title","release","album title","project title") or title
    sheets={"Master Tracklist New": sheet}
    sheets.update(additional_sheets or {})
    if any(get(row,"contributor","contributor name","writer","songwriter","publisher") for row in track_rows):
        sheets["Royalty Split Sheets"]=[list(headers)] + [list(row) for row in values]
    return _import_release_sheets(actor=actor, organization=organization, artist=artist, sheets=sheets, title=tracker_title, release_date=release_date, request=request)

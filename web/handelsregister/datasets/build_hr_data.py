"""
From the original dump
fill the stelselpedia dumps
"""
import datetime
import logging
import time
from decimal import Decimal
from typing import List, Union

from django import db
from django.conf import settings
from django.db import transaction

from datasets.hr.models import Communicatiegegevens, Locatie, CommercieleVestiging, \
    NietCommercieleVestiging, Activiteit
from datasets.hr.models import Functievervulling
from datasets.hr.models import Persoon
from datasets.hr.models import Vestiging
from datasets.kvkdump.models import KvkFunctievervulling, KvkAdres
from datasets.kvkdump.models import KvkMaatschappelijkeActiviteit
from datasets.kvkdump.models import KvkPersoon
from datasets.kvkdump.models import KvkVestiging

BAG_NUMMERAANDUIDING = "https://api.datapunt.amsterdam.nl/bag/nummeraanduiding/{}/"
BAG_VERBLIJFSOBJECT = "https://api.datapunt.amsterdam.nl/bag/verblijfsobject/{}/"

log = logging.getLogger(__name__)


class BatchImport(object):
    item_handle = None
    queryset = None
    batch_size = 4000

    def batch_qs(self):
        """
        Returns a (start, end, total, queryset) tuple
        for each batch in the given queryset.

        Usage:
            # Make sure to order your querset!
            article_qs = Article.objects.order_by('id')
            for start, end, total, qs in batch_qs(article_qs):
                print "Now processing %s - %s of %s" % (start + 1, end, total)
                for article in qs:
                    print article.body
        """
        qs = self.queryset

        batch_size = self.batch_size

        numerator = settings.PARTIAL_IMPORT['numerator']
        denominator = settings.PARTIAL_IMPORT['denominator']

        log.info("STARTING BATCHER JOB: %s" % (self.__class__.__name__))
        log.info("PART: %s OF %s" % (numerator + 1, denominator))

        end_part = count = total = qs.count()
        chunk_size = batch_size

        start_index = 0

        # Do partial import
        if denominator > 1:
            chunk_size = int(total / denominator)
            start_index = numerator * chunk_size
            end_part = (numerator + 1) * chunk_size
            total = end_part - start_index

        log.info("START: %s END %s COUNT: %s CHUNK %s TOTAL_COUNT: %s" % (
            start_index, end_part, chunk_size, batch_size, count))

        # total batches in this (partial) bacth job
        total_batches = int(chunk_size / batch_size)

        for i, start in enumerate(range(start_index, end_part, batch_size)):
            end = min(start + batch_size, end_part)
            t_start = time.time()
            yield (i + 1, total_batches + 1, start, end, total, qs[start:end])
            log.info("CHUNK %5s - %-5s  in %.3f seconds" % (
                start, end, time.time() - t_start))

    def process_rows(self):
        for job, end_job, start, end, total, qs in self.batch_qs():
            with transaction.atomic():
                for item in qs:
                    self.process_item(item)

    def process_item(self, item):
        """
        Handle a single item/row.
        """
        raise NotImplementedError()


def _as_adres(a: KvkAdres) -> Locatie:
    loc = Locatie(
        id=str(a.adrid),
        volledig_adres=a.volledigadres,
        toevoeging_adres=a.toevoegingadres,
        afgeschermd=_parse_indicatie(a.afgeschermd),
        postbus_nummer=a.postbusnummer,
        straat_huisnummer=a.straathuisnummer,
        postcode_woonplaats=a.postcodewoonplaats,
        regio=a.regio,
        land=a.land,
        geometry=a.geopunt,
    )

    if a.identificatieaoa:
        loc.bag_nummeraanduiding = BAG_NUMMERAANDUIDING.format(a.identificatieaoa)

    if a.identificatietgo:
        loc.bag_adresseerbaar_object = BAG_VERBLIJFSOBJECT.format(a.identificatietgo)

    loc.save()
    return loc


def _as_communicatiegegevens(m: Union[KvkMaatschappelijkeActiviteit, KvkVestiging]) -> List[Communicatiegegevens]:
    cg1, cg2, cg3 = None, None, None
    if m.domeinnaam1 or m.emailadres1 or m.nummer1:
        cg1 = Communicatiegegevens(
            domeinnaam=m.domeinnaam1,
            emailadres=m.emailadres1,
            toegangscode=m.toegangscode1,
            communicatie_nummer=m.nummer1,
            soort_communicatie_nummer=m.soort1,
        )
    if m.domeinnaam2 or m.emailadres2 or m.nummer2:
        cg2 = Communicatiegegevens(
            domeinnaam=m.domeinnaam2,
            emailadres=m.emailadres2,
            toegangscode=m.toegangscode2,
            communicatie_nummer=m.nummer2,
            soort_communicatie_nummer=m.soort2,
        )
    if m.domeinnaam3 or m.emailadres3 or m.nummer3:
        cg3 = Communicatiegegevens(
            domeinnaam=m.domeinnaam3,
            emailadres=m.emailadres3,
            toegangscode=m.toegangscode3,
            communicatie_nummer=m.nummer3,
            soort_communicatie_nummer=m.soort3,
        )

    return [c for c in (cg1, cg2, cg3) if c]


def __clean_code(code: Decimal) -> str:
    result = str(code)
    if result == '900302':
        return '9003'
    elif result == '889922':
        return '88992'
    elif result == '620202':
        return '6202'
    else:
        return result


def _as_activiteiten(v: KvkVestiging) -> List[Activiteit]:
    a1, a2, a3, a4 = None, None, None, None
    if v.sbicodehoofdactiviteit:
        a1 = Activiteit(
            activiteitsomschrijving=v.omschrijvingactiviteit,
            sbi_code=__clean_code(v.sbicodehoofdactiviteit),
            sbi_omschrijving=v.sbiomschrijvinghoofdact,
            hoofdactiviteit=True,
        )

    if v.sbicodenevenactiviteit1:
        a2 = Activiteit(
            sbi_code=__clean_code(v.sbicodenevenactiviteit1),
            sbi_omschrijving=v.sbiomschrijvingnevenact1,
            hoofdactiviteit=False,
        )

    if v.sbicodenevenactiviteit2:
        a3 = Activiteit(
            sbi_code=__clean_code(v.sbicodenevenactiviteit2),
            sbi_omschrijving=v.sbiomschrijvingnevenact2,
            hoofdactiviteit=False,
        )

    if v.sbicodenevenactiviteit3:
        a4 = Activiteit(
            sbi_code=__clean_code(v.sbicodenevenactiviteit3),
            sbi_omschrijving=v.sbiomschrijvingnevenact3,
            hoofdactiviteit=False,
        )

    return [a for a in (a1, a2, a3, a4) if a]


def _parse_decimal_date(d: Decimal) -> datetime.date:
    if not d:
        return None

    return datetime.datetime.strptime(str(d), "%Y%m%d")


def _parse_indicatie(s: str) -> bool:
    return bool(s and s.lower() == 'ja')


def load_ves_row(v: KvkVestiging) -> Vestiging:
    if False and v.sbicodenevenactiviteit2:
        print(v)
        import sys
        sys.exit()

    ves = Vestiging.objects.create(
        id=v.vesid,
        maatschappelijke_activiteit_id=v.maatschappelijke_activiteit_id,
        vestigingsnummer=v.vestigingsnummer,
        hoofdvestiging=_parse_indicatie(v.indicatiehoofdvestiging),
        naam=v.eerstehandelsnaam or v.naam,
        datum_aanvang=_parse_decimal_date(v.datumaanvang),
        datum_einde=_parse_decimal_date(v.datumeinde),
    )

    if v.typeringvestiging == "CVS":
        cvs = CommercieleVestiging.objects.create(
            totaal_werkzame_personen=v.totaalwerkzamepersonen,
            parttime_werkzame_personen=v.parttimewerkzamepersonen,
            fulltime_werkzame_personen=v.fulltimewerkzamepersonen,
            import_activiteit=_parse_indicatie(v.importactiviteit),
            export_activiteit=_parse_indicatie(v.exportactiviteit),
        )
        ves.commerciele_vestiging = cvs
    elif v.typeringvestiging == "NCV":
        ncv = NietCommercieleVestiging.objects.create(
            ook_genoemd=v.ookgenoemd,
            verkorte_naam=v.verkortenaam,
        )
        ves.niet_commerciele_vestiging = ncv
    else:
        raise ValueError("Unknown typering {}".format(v.typeringvestiging))

    for kvk_adres in v.adressen.all():
        if kvk_adres.typering == 'bezoekLocatie':
            ves.bezoekadres = _as_adres(kvk_adres)

        if kvk_adres.typering == 'postLocatie':
            ves.postadres = _as_adres(kvk_adres)

    communicatiegegevens = _as_communicatiegegevens(v)
    for c in communicatiegegevens:
        c.save()
    ves.communicatiegegevens.add(*communicatiegegevens)

    activiteiten = _as_activiteiten(v)
    for a in activiteiten:
        a.save()
    ves.activiteiten.add(*activiteiten)

    ves.save()

    return ves


def load_prs_row(prs_object):
    p = prs_object
    Persoon.objects.create(
        prsid=p.prsid,
        rechtsvorm=p.rechtsvorm,
        uitgebreide_rechtsvorm=p.uitgebreiderechtsvorm,
        volledige_naam=p.volledigenaam,
    )


def load_functievervulling_row(functievervulling_object):
    f = functievervulling_object
    Functievervulling.objects.create(
        fvvid=f.ashid,
        functietitel=f.functie
    )


class VESbatcher(BatchImport):
    queryset = KvkVestiging.objects.order_by('vesid')

    def process_item(self, item):
        load_ves_row(item)


class PRSbatcher(BatchImport):
    queryset = KvkPersoon.objects.order_by('prsid')

    def process_item(self, item):
        load_prs_row(item)


class FunctievervullingBatcher(BatchImport):
    queryset = KvkFunctievervulling.objects.all().order_by('ashid')

    def process_item(self, item):
        load_functievervulling_row(item)


def fill_stelselpedia():
    """
    Go through all tables and fill Stelselpedia tables.
    """
    with db.connection.cursor() as cursor:
        log.info("Converteren locaties")
        _converteer_locaties(cursor)

        log.info("Converteren onderneming")
        _converteer_onderneming(cursor)

        log.info("Converteren maatschappelijke activiteit")
        _converteer_maatschappelijke_activiteit(cursor)

        log.info("Converteren handelsnaam")
        _converteer_handelsnaam(cursor)

        for i in (1, 2, 3):
            log.info("Converteren communicatie-gegevens-{0}".format(i))
            _converteer_communicatiegegevens(cursor, i)

            # MACbatcher().process_rows()
            # PRSbatcher().process_rows()
            # VESbatcher().process_rows()
            # FunctievervullingBatcher().process_rows()


def _converteer_locaties(cursor):
    cursor.execute("""
INSERT INTO hr_locatie (
  id,
  volledig_adres,
  toevoeging_adres,
  afgeschermd,
  postbus_nummer,
  bag_nummeraanduiding,
  bag_adresseerbaar_object,
  straat_huisnummer,
  postcode_woonplaats,
  regio,
  land,
  geometry
)
    SELECT
      adrid,
      volledigadres,
      toevoegingadres,
      CASE afgeschermd
        WHEN 'Ja' THEN TRUE
        ELSE FALSE
      END,
      postbusnummer,
      'https://api.datapunt.amsterdam.nl/bag/nummeraanduiding/' || identificatieaoa || '/',
      'https://api.datapunt.amsterdam.nl/bag/verblijfsobject/' || identificatietgo || '/',
      straathuisnummer,
      postcodewoonplaats,
      regio,
      land,
      geopunt
    FROM kvkadrm00
        """)


def _converteer_onderneming(cursor):
    cursor.execute("""
INSERT INTO hr_onderneming (
  id,
  totaal_werkzame_personen,
  fulltime_werkzame_personen,
  parttime_werkzame_personen
)
  SELECT
    macid,
    totaalwerkzamepersonen,
    fulltimewerkzamepersonen,
    parttimewerkzamepersonen
  FROM kvkmacm00
  WHERE indicatieonderneming = 'Ja'
        """)


def _converteer_maatschappelijke_activiteit(cursor):
    cursor.execute("""
INSERT INTO hr_maatschappelijkeactiviteit (
  id,
  naam,
  kvk_nummer,
  datum_aanvang,
  datum_einde,
  incidenteel_uitlenen_arbeidskrachten,
  non_mailing,
  onderneming_id,
  postadres_id,
  bezoekadres_id
  --   eigenaar_id, hoofdvestiging_id
)
  SELECT
    m.macid,
    m.naam,
    m.kvknummer,
    to_date(to_char(m.datumaanvang, '99999999'), 'YYYYMMDD'),
    to_date(to_char(m.datumeinde, '99999999'), 'YYYYMMDD'),
    NULL,
    CASE m.nonmailing
    WHEN 'Ja'
      THEN TRUE
    WHEN 'Nee'
      THEN FALSE
    ELSE NULL
    END,
    CASE m.indicatieonderneming
    WHEN 'Ja'
      THEN m.macid
    ELSE NULL
    END,
    p.adrid,
    b.adrid
  FROM kvkmacm00 m
    LEFT JOIN kvkadrm00 p ON p.macid = m.macid AND p.typering = 'postLocatie'
    LEFT JOIN kvkadrm00 b ON b.macid = m.macid AND b.typering = 'bezoekLocatie'
        """)


def _converteer_handelsnaam(cursor):
    cursor.execute("""
INSERT INTO hr_handelsnaam (id, handelsnaam, onderneming_id)
  SELECT
    hdnid,
    handelsnaam,
    macid
  FROM kvkhdnm00
        """)


def _converteer_communicatiegegevens(cursor, i):
    cursor.execute("""
INSERT INTO hr_communicatiegegevens (
  id,
  domeinnaam,
  emailadres,
  toegangscode,
  communicatie_nummer,
  soort_communicatie_nummer
)
  SELECT
    macid || '1',
    domeinnaam1,
    emailadres1,
    toegangscode1,
    nummer1,
    soort1
  FROM kvkmacm00
  WHERE domeinnaam1 IS NOT NULL
        OR emailadres1 IS NOT NULL
        OR toegangscode1 IS NOT NULL
        OR nummer1 IS NOT NULL
        OR soort1 IS NOT NULL
            """.replace('1', str(i)))
    cursor.execute("""
INSERT INTO hr_maatschappelijkeactiviteit_communicatiegegevens (
  maatschappelijkeactiviteit_id,
  communicatiegegevens_id
)
  SELECT
    macid,
    macid || '1'
  FROM kvkmacm00
  WHERE domeinnaam1 IS NOT NULL
        OR emailadres1 IS NOT NULL
        OR toegangscode1 IS NOT NULL
        OR nummer1 IS NOT NULL
        OR soort1 IS NOT NULL
            """.replace('1', str(i)))

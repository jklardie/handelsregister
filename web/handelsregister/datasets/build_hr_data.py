"""
From the original dump
fill the stelselpedia dumps
"""
import logging

from django import db

from django.conf import settings

log = logging.getLogger(__name__)


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
            log.info("Converteren MAC communicatie-gegevens-{0}".format(i))
            _converteer_mac_communicatiegegevens(cursor, i)

        log.info("Converteren commerciële vestiging")
        _converteer_commerciele_vestiging(cursor)

        log.info("Converteren niet-commerciële vestiging")
        _converteer_niet_commerciele_vestiging(cursor)

        log.info("Converteren vestiging")
        _converteer_vestiging(cursor)

        for i in (1, 2, 3):
            log.info("Converteren VES communicatie-gegevens-{0}".format(i))
            _converteer_ves_communicatiegegevens(cursor, i)

        log.info("Converteren hoofdactiviteit")
        _converteer_hoofdactiviteit(cursor)
        for i in (1, 2, 3):
            log.info("Converteren nevenactiviteit-{0}".format(i))
            _converteer_nevenactiviteit(cursor, i)

        log.info("Converteren handelsnaam vestiging")
        _converteer_handelsnaam_ves(cursor)

        log.info("Converteren hoofdvestiging")
        _converteer_hoofdvestiging(cursor)

        log.info("Converteren natuurlijk_persoon")
        _converteer_natuurlijk_persoon(cursor)

        log.info("Converteren NIET natuurlijk_persoon")
        _converteer_niet_natuurlijk_persoon(cursor)

        log.info("Converteren persoon")
        _converteer_persoon(cursor)

        log.info("Converteren functievervulling")
        _converteer_functievervulling(cursor)

        log.info("Converteer eigenaren")
        _converteer_mac_eigenaar_id(cursor)

        # eigenaren zitten niet in zonde export..
        log.info("Converteer onbekende mac mks eigenaren")
        _converteer_onbekende_mac_eigenaar_id(cursor)


def _converteer_locaties(cursor):
    cursor.execute("""
INSERT INTO hr_locatie (
  id,
  volledig_adres,
  toevoeging_adres,
  afgeschermd,
  postbus_nummer,
  bag_numid,
  bag_vbid,
  bag_nummeraanduiding,
  bag_adresseerbaar_object,
  straat_huisnummer,
  postcode_woonplaats,
  regio,
  land,
  geometrie
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
      identificatieaoa,
      identificatietgo,
      'https://api.datapunt.amsterdam.nl/bag/nummeraanduiding/' ||
            identificatieaoa || '/',
      'https://api.datapunt.amsterdam.nl/bag/verblijfsobject/' ||
            identificatietgo || '/',
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
INSERT INTO hr_handelsnaam (id, handelsnaam)
  SELECT
    hdnid,
    handelsnaam
  FROM kvkhdnm00
        """)

    cursor.execute("""
INSERT INTO hr_onderneming_handelsnamen(onderneming_id, handelsnaam_id)
  SELECT
    macid,
    hdnid
  FROM kvkhdnm00
    """)


def _converteer_handelsnaam_ves(cursor):
    cursor.execute("""
INSERT INTO hr_vestiging_handelsnamen(vestiging_id, handelsnaam_id)
  SELECT
    vh.vesid,
    h.hdnid
  FROM kvkveshdnm00 vh LEFT JOIN kvkhdnm00 h ON vh.veshdnid = h.hdnid
  WHERE h.hdnid IS NOT NULL
    """)


def _converteer_mac_communicatiegegevens(cursor, i):
    _converteer_any_communicatiegegevens(
        cursor, i, 'macid', 'kvkmacm00', 'maatschappelijkeactiviteit')


def _converteer_ves_communicatiegegevens(cursor, i):
    _converteer_any_communicatiegegevens(
        cursor, i, 'vesid', 'kvkvesm00', 'vestiging')


def _converteer_any_communicatiegegevens(
        cursor, i, id_col, source, target):
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
    {id_col} || '{index}',
    domeinnaam{index},
    emailadres{index},
    toegangscode{index},
    nummer{index},
    soort{index}
  FROM {source}
  WHERE domeinnaam{index} IS NOT NULL
        OR emailadres{index} IS NOT NULL
        OR toegangscode{index} IS NOT NULL
        OR nummer{index} IS NOT NULL
        OR soort{index} IS NOT NULL
            """.format(id_col=id_col, source=source, index=i))
    cursor.execute("""
INSERT INTO hr_{target}_communicatiegegevens (
  {target}_id,
  communicatiegegevens_id
)
  SELECT
    {id_col},
    {id_col} || '{index}'
  FROM {source}
  WHERE domeinnaam{index} IS NOT NULL
        OR emailadres{index} IS NOT NULL
        OR toegangscode{index} IS NOT NULL
        OR nummer{index} IS NOT NULL
        OR soort{index} IS NOT NULL
            """.format(id_col=id_col, source=source, target=target, index=i))


def _converteer_commerciele_vestiging(cursor):
    cursor.execute("""
INSERT INTO hr_commercielevestiging (
  id,
  totaal_werkzame_personen,
  fulltime_werkzame_personen,
  parttime_werkzame_personen,
  import_activiteit,
  export_activiteit
)
  SELECT
    vesid,
    totaalwerkzamepersonen,
    fulltimewerkzamepersonen,
    parttimewerkzamepersonen,
    CASE importactiviteit
    WHEN 'Ja'
      THEN TRUE
    WHEN 'Nee'
      THEN FALSE
    ELSE NULL END,
    CASE exportactiviteit
    WHEN 'Ja'
      THEN TRUE
    WHEN 'Nee'
      THEN FALSE
    ELSE NULL END
  FROM kvkvesm00
  WHERE typeringvestiging = 'CVS'
      """)


def _converteer_niet_commerciele_vestiging(cursor):
    cursor.execute("""
INSERT INTO hr_nietcommercielevestiging (
  id,
  ook_genoemd,
  verkorte_naam
)
  SELECT
    vesid,
    ookgenoemd,
    verkortenaam
  FROM kvkvesm00
  WHERE typeringvestiging = 'NCV'
      """)


def _converteer_vestiging(cursor):
    cursor.execute("""
INSERT INTO hr_vestiging
(
  id,
  vestigingsnummer,
  hoofdvestiging,
  naam,
  datum_aanvang,
  datum_einde,
  datum_voortzetting,
  maatschappelijke_activiteit_id,
  commerciele_vestiging_id,
  niet_commerciele_vestiging_id,
  bezoekadres_id,
  postadres_id
)

  SELECT
    v.vesid,
    v.vestigingsnummer,
    CASE v.indicatiehoofdvestiging
    WHEN 'Ja'
      THEN TRUE
    ELSE FALSE
    END,

    coalesce(v.naam, v.eerstehandelsnaam),
    to_date(to_char(v.datumaanvang, '99999999'), 'YYYYMMDD'),
    to_date(to_char(v.datumeinde, '99999999'), 'YYYYMMDD'),
    NULL,

    v.macid,
    CASE v.typeringvestiging
    WHEN 'CVS'
      THEN v.vesid
    ELSE NULL END,
    CASE v.typeringvestiging
    WHEN 'NCV'
      THEN v.vesid
    ELSE NULL END,
    b.adrid,
    p.adrid
  FROM kvkvesm00 v
    LEFT JOIN kvkadrm00 p ON p.vesid = v.vesid AND p.typering = 'postLocatie'
    LEFT JOIN kvkadrm00 b ON b.vesid = v.vesid AND b.typering = 'bezoekLocatie'
        """)


def _converteer_hoofdactiviteit(cursor):
    cursor.execute("""
INSERT INTO hr_activiteit (
  id,
  activiteitsomschrijving,
  sbi_code,
  sbi_omschrijving,
  hoofdactiviteit
)
  SELECT
    vesid || '0',
    omschrijvingactiviteit,
    CASE sbicodehoofdactiviteit
    WHEN '900302' THEN '9003'
    WHEN '889922' THEN '88992'
    WHEN '620202' THEN '6202'
    ELSE sbicodehoofdactiviteit END ,
    sbiomschrijvinghoofdact,
    TRUE
  FROM kvkvesm00
  WHERE sbicodehoofdactiviteit IS NOT NULL
    """)
    cursor.execute("""
INSERT INTO hr_vestiging_activiteiten (
  vestiging_id,
  activiteit_id
)
  SELECT
    vesid,
    vesid || '0'
  FROM kvkvesm00
  WHERE sbicodehoofdactiviteit IS NOT NULL
    """)


def _converteer_nevenactiviteit(cursor, i):
    cursor.execute("""
INSERT INTO hr_activiteit (
  id,
  sbi_code,
  sbi_omschrijving,
  hoofdactiviteit
)
  SELECT
    vesid || '{index}',
    CASE sbicodenevenactiviteit{index}
    WHEN '900302' THEN '9003'
    WHEN '889922' THEN '88992'
    WHEN '620202' THEN '6202'
    ELSE sbicodenevenactiviteit{index} END ,
    sbiomschrijvingnevenact{index},
    FALSE
  FROM kvkvesm00
  WHERE sbicodenevenactiviteit{index} IS NOT NULL
    """.format(index=i))

    cursor.execute("""
INSERT INTO hr_vestiging_activiteiten (
  vestiging_id,
  activiteit_id
)
  SELECT
    vesid,
    vesid || '{index}'
  FROM kvkvesm00
  WHERE sbicodenevenactiviteit{index}  IS NOT NULL
    """.format(index=i))


def _converteer_hoofdvestiging(cursor):
    cursor.execute("""
UPDATE hr_maatschappelijkeactiviteit m
SET hoofdvestiging_id = v.id
FROM hr_vestiging v
WHERE v.maatschappelijke_activiteit_id = m.id
  AND v.hoofdvestiging
    """)


def _converteer_persoon(cursor):
    cursor.execute("""
INSERT INTO hr_persoon (
    id,
    typering,
    rol,
    rechtsvorm,
    uitgebreide_rechtsvorm,
    volledige_naam,
    soort,
    reden_insolvatie,
    datumuitschrijving,
    nummer,
    toegangscode,
    faillissement,
    natuurlijkpersoon_id,
    niet_natuurlijkpersoon_id
) SELECT
    prsid,
    typering,
    rol,
    persoonsrechtsvorm,
    uitgebreiderechtsvorm,
    volledigenaam,
    soort,
    redeninsolvatie,
    to_date(to_char(datumuitschrijving, '99999999'), 'YYYYMMDD'),
    nummer,
    toegangscode,
    CASE faillissement
        WHEN 'Ja' THEN TRUE
        ELSE FALSE
    END,
    CASE typering
        WHEN 'natuurlijkPersoon' THEN prsid
        ELSE null
    END,
    CASE typering != 'natuurlijkPersoon'
        WHEN true THEN prsid
        ELSE null
    END
  FROM kvkprsm00
    """)


def _converteer_natuurlijk_persoon(cursor):

    cursor.execute("""
INSERT INTO hr_natuurlijkpersoon (
    id,
    geslachtsnaam,
    geslachtsaanduiding,
    voornamen,
    huwelijksdatum,
    geboortedatum,
    geboorteplaats,
    geboorteland
) SELECT
    prsid,
    geslachtsnaam,
    geslachtsaanduiding,
    voornamen,
    to_date(to_char(huwelijksdatum, '99999999'), 'YYYYMMDD'),
    to_date(to_char(geboortedatum, '99999999'), 'YYYYMMDD'),
    geboorteplaats,
    geboorteland
  FROM kvkprsm00 WHERE typering = 'natuurlijkPersoon'
    """)


def _converteer_niet_natuurlijk_persoon(cursor):

    cursor.execute("""
INSERT INTO hr_nietnatuurlijkpersoon (
    id,
    rsin,
    verkorte_naam,
    ook_genoemd
) SELECT
    prsid,
    rsin,
    verkortenaam,
    ookgenoemd
  FROM kvkprsm00 WHERE typering != 'natuurlijkPersoon'
    """)


def _converteer_functievervulling(cursor):
    cursor.execute("""
INSERT INTO hr_functievervulling (
    id,
    functietitel,
    heeft_aansprakelijke_id,
    is_aansprakelijke_id,
    soortbevoegdheid
) SELECT
    ashid,
    functie,
    prsidh,
    prsidi,
    soort
  FROM kvkprsashm00
    """)


def _converteer_mac_eigenaar_id(cursor):
    cursor.execute("""
UPDATE hr_maatschappelijkeactiviteit hrm
SET eigenaar_id = m.prsid
FROM kvkmacm00 m
WHERE m.macid = hrm.id AND EXISTS (
    select * from hr_persoon WHERE id = m.prsid)
    """)


def _converteer_onbekende_mac_eigenaar_id(cursor):
    cursor.execute("""
UPDATE hr_maatschappelijkeactiviteit hrm
SET eigenaar_mks_id = m.prsid
FROM kvkmacm00 m
WHERE m.macid = hrm.id AND NOT EXISTS (
    select * from hr_persoon WHERE id = m.prsid)
    """)

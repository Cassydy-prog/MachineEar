

# Data Sources and PDF Licences

MachineEar uses 12 technical PDFs covering fan maintenance, pump operation,
troubleshooting, and bearing inspection.

The collection contains 835 physical PDF pages. The RAG index uses 828 eligible
pages, divided into 3,353 passages.

## Fan and Bearing Documents

Files are stored in `data/manuals/Fan_Docs/`.

| PDF filename | Document | Publisher | Edition |
| --- | --- | --- | --- |
| `463687CentFans_iom.pdf` | Industrial Process Fans — Model IP, Document 463687 | Greenheck Fan Corporation | Revision 12, April 2022 |
| `Centrifugal-Fans-IM-995.pdf` | Centrifugal Fans — Installation, Operation & Maintenance Manual | Twin City Fan Companies, Ltd. | April 2020 |
| `Fans-with-CE-Mark-French-IM-2-06.pdf` | Ventilateurs avec marquage CE — Manuel d’installation, d’utilisation et d’entretien | Twin City Fan Companies, Ltd. | March 2022 |
| `Inline-Centrifugal-Mixed-Flow-Fans-IM-895.pdf` | Inline Centrifugal and Mixed Flow Fans | Twin City Fan Companies, Ltd. | August 2022 |
| `Inline-Fume-Exhaust-Fans-IM-1080.pdf` | Inline Fume Exhaust Fans | Twin City Fan Companies, Ltd. | January 2025 |
| `Troubleshooting-Maintenance-Guides-1.pdf` | Industrial Fan Troubleshooting Guide and Preventive Maintenance Guide | AirPro Fan & Blower Company | No printed issue date |
| `Troubleshooting-Vibration-Problems-ES-202-1.pdf` | Troubleshooting Vibration Problems — ES-202 | Twin City Fan & Blower | April 1998 |
| `wl_82102_2_de_en.pdf` | Rolling Bearing Damage: Recognition of Damage and Bearing Inspection | FAG Kugelfischer AG, Schaeffler Group | 2003 |

## Pump Documents

Files are stored in `data/manuals/Pump_Docs/`.

| PDF filename | Document | Publisher | Edition |
| --- | --- | --- | --- |
| `001080070g_c_10_2025_e-nsc_goulds-wt.pdf` | e-NSC Series — Horizontal Centrifugal Electric Pumps: Installation, Operation and Maintenance Manual | Xylem | October 2025 |
| `1710_iom_02_2023.pdf` | Series 1710 — Installation, Operation, and Maintenance Manual | Xylem | Document dated December 2022; PDF metadata February 2023 |
| `p2002569b-1.pdf` | Series A-C 2000 Closed-Coupled Pumps — Instruction Manual | Xylem / Goulds Water Technology | Revision B, February 2019 |
| `pump.pdf` | Improving Pumping System Performance: A Sourcebook for Industry, Second Edition | U.S. Department of Energy and Hydraulic Institute; produced by NREL | May 2006 |

## Publisher References

These publisher websites or catalogue references appear in the documents.
They are not verified original download URLs. Historical addresses may have moved.

| Publisher | Website or catalogue |
| --- | --- |
| Greenheck | https://www.greenheck.com/Resources/Library/Literature |
| Twin City Fan | https://www.tcf.com/resources/im-manuals |
| AirPro Fan & Blower | https://airprofan.com |
| FAG | http://www.fag.com — historical address printed in the document |
| Xylem | https://www.xylem.com |
| Goulds Water Technology | https://www.xylem.com/gouldswatertechnology |
| U.S. Department of Energy | http://www.eere.energy.gov/industry — historical address printed in the sourcebook |

## Copyright and Licence Information

No explicit open licence was identified in the supplied PDF copies.
Public availability does not establish permission to redistribute a document.

| Document | Rights evidence in the PDF |
| --- | --- |
| Greenheck Industrial Process Fans | Copyright © 2022 Greenheck Fan Corporation; physical page 16. No explicit reuse licence found. |
| Twin City Fan IM-995 | Copyright © 2017–2020 Twin City Fan Companies, Ltd.; physical page 32. No explicit reuse licence found. |
| Twin City Fan IM-2-06 | Copyright © 2006–2022 Twin City Fan Companies, Ltd.; physical page 1. No explicit reuse licence found. |
| Twin City Fan IM-895 | Copyright © 2004–2022 Twin City Fan Companies, Ltd.; physical page 20. No explicit reuse licence found. |
| Twin City Fan IM-1080 | Copyright © 2012–2025 Twin City Fan Companies, Ltd.; physical page 24. No explicit reuse licence found. |
| AirPro troubleshooting and maintenance guides | No explicit reuse licence identified on the two visually inspected pages. |
| Twin City Fan ES-202 | No explicit reuse licence identified in the one-page document. |
| FAG Rolling Bearing Damage | Copyright © FAG 2003; physical page 74 explicitly states that reproduction of the publication or parts requires permission. |
| Xylem e-NSC | Copyright © 2025 Xylem Inc. or its affiliates. All rights reserved; physical page 464. |
| Xylem Series 1710 | Copyright © 2022 Xylem; physical page 32. No explicit reuse licence found. |
| Xylem A-C 2000 | Copyright © 2019 Xylem, Inc.; physical page 32. No explicit reuse licence found. |
| DOE pumping sourcebook | No explicit reuse licence identified. Government sponsorship alone does not establish that all contributed text and photographs are public domain. |

The Goulds trademark references to use “under license” concern the trademark;
they do not grant a licence to redistribute the manuals.

This register documents the evidence found. It does not grant reuse permission
or apply the project's software licence to third-party PDFs.

## Use in MachineEar

The manuals supply reference passages for maintenance-document retrieval.

| Processing stage | Purpose |
| --- | --- |
| Text extraction | Extract native PDF text and recognize scanned text using local OCR |
| Chunking | Create passages capped at 480 tokens and 350 words, with up to 40 overlapping words |
| Indexing | Store semantic vectors and a keyword-search index |
| Retrieval | Combine semantic and BM25 rankings using Reciprocal Rank Fusion |
| Source verification | Preserve document names, physical page numbers, exact text, and checksums |

Original PDFs remain unchanged. Unproofread OCR and review-flagged pages are
excluded from default retrieval.

## Verification Status

The local review inspected PDF text, metadata, source references, and copyright
notices. Both image-only AirPro pages were visually inspected.

Publisher website checks were blocked by the cloud environment's proxy with
HTTP 403 responses. Online terms and original download locations therefore
remain unverified.


"""Synthetic data for a fictional server manufacturer's RMA (warranty return) desk.

- data/installed_base.csv: every shipped server: serial, model, customer, ship date, warranty term
- data/requests.csv: 480 inbound support emails in English and French, with the
  ground truth an RMA analyst would assign (is it an RMA? which failure category?
  which serials? is it a safety issue?). Some are not RMA requests at all, some
  have no serial, some quote a serial the sender does not own, some are out of
  warranty, some describe smoke or burning, and some are written sloppily.
- data/baseline_log.csv: how the current manual process handled each request
  (timestamps and errors), used as the before picture.
"""
import csv
import random
from datetime import date, datetime, timedelta
from pathlib import Path

SEED = 23
OUT = Path("data")
MODELS = ["Corvus R2", "Corvus R4", "Arcline A8", "Tidepool IM1"]
CUSTOMERS = {"northwind-analytics.com": "Northwind Analytics", "laval-render.ca": "Laval Render Farm",
             "polaris-bio.com": "Polaris Bio", "quantumleaf.io": "QuantumLeaf AI",
             "fleuve-donnees.qc.ca": "Fleuve Données", "metro-health.org": "Metro Health Network"}

CATEGORY_EN = {
    "PSU": ["power supply {u} on the unit is dead", "PSU fault light is amber and the node won't power on",
            "one of the redundant power supplies failed", "server shuts down, PSU {u} reports failure"],
    "MEMORY": ["getting uncorrectable ECC errors on DIMM slot {u}", "memory errors in the event log, DIMM {u} flagged",
               "the box keeps rebooting with memory training failures", "bad RAM module, DIMM {u} disabled at POST"],
    "STORAGE": ["NVMe drive in bay {u} is not detected", "SSD failure, RAID is degraded",
                "drive {u} shows predictive failure", "disk backplane reports a failed drive in slot {u}"],
    "MOTHERBOARD": ["system board fails POST with code {u}", "no video and no POST, suspect the motherboard",
                    "BMC unreachable and board won't initialize", "mainboard error, CPU socket {u} not detected"],
    "COOLING": ["fan {u} failed and the node is thermal throttling", "coolant temperature alarm on the immersion tank",
                "overheating, fans spinning at max then shutdown", "thermal shutdown after fan module {u} stopped"],
    "NETWORK": ["the 100G NIC is down, no link on port {u}", "network card not detected after reboot",
                "NIC firmware crashed and port {u} flaps constantly", "Mellanox card throws link errors on port {u}"],
    "DOA": ["brand new unit arrived dead on arrival", "just received the server and it never powered on",
            "out of the box it does not boot at all", "new delivery, DOA, nothing on the console"],
}
CATEGORY_FR = {
    "PSU": ["le bloc d'alimentation {u} est mort", "voyant d'alimentation orange, le noeud ne démarre plus",
            "une des alimentations redondantes a lâché"],
    "MEMORY": ["erreurs ECC non corrigibles sur la barrette {u}", "erreurs mémoire dans le journal, DIMM {u} signalée",
               "le serveur redémarre en boucle, erreur d'initialisation mémoire"],
    "STORAGE": ["le disque NVMe de la baie {u} n'est plus détecté", "panne de SSD, le RAID est dégradé",
                "le disque {u} annonce une défaillance imminente"],
    "MOTHERBOARD": ["la carte mère échoue au POST avec le code {u}", "pas d'image, pas de POST, carte mère suspecte",
                    "le BMC est injoignable et la carte ne s'initialise pas"],
    "COOLING": ["le ventilateur {u} est en panne et le noeud surchauffe", "alarme de température du liquide dans la cuve d'immersion",
                "surchauffe, arrêt thermique après la panne du module de ventilation {u}"],
    "NETWORK": ["la carte réseau 100G ne fonctionne plus, aucun lien sur le port {u}", "la carte réseau n'est plus détectée après redémarrage",
                "le port {u} de la carte réseau tombe sans arrêt"],
    "DOA": ["l'unité neuve est arrivée hors service", "serveur reçu hier, il ne s'est jamais allumé",
            "neuf, ne démarre pas du tout à la sortie de la boîte"],
}
NON_RMA_EN = ["Can you send me an updated quote for {n} more {m} nodes?", "What is the status of our order PO-{n}?",
              "Our invoice INV-{n} seems to have the wrong billing address.", "Is there a newer BIOS for the {m}? Release notes please.",
              "We'd like to schedule a site visit to discuss the next expansion."]
NON_RMA_FR = ["Pouvez-vous m'envoyer une soumission pour {n} noeuds {m} de plus?", "Où en est notre commande PO-{n}?",
              "La facture INV-{n} a la mauvaise adresse de facturation.", "Existe-t-il un nouveau BIOS pour le {m}?"]
SAFETY_EN = ["we smelled burning and saw smoke from the chassis", "there was a spark and a burning smell from the PSU"]
SAFETY_FR = ["odeur de brûlé et fumée qui sort du châssis", "une étincelle et une odeur de brûlé près de l'alimentation"]


def serial(rng):
    return f"HT{rng.randint(10, 26)}-{rng.randint(100000, 999999)}"


def main():
    rng = random.Random(SEED)
    OUT.mkdir(exist_ok=True)
    base = []
    for domain, name in CUSTOMERS.items():
        for _ in range(rng.randint(40, 70)):
            ship = date(2026, 10, 1) - timedelta(days=rng.randint(10, 30 * 30) if rng.random() < 0.85 else rng.randint(36 * 30, 6 * 365))
            base.append({"serial": serial(rng), "model": rng.choice(MODELS), "customer_domain": domain,
                         "customer": name, "ship_date": ship.isoformat(), "warranty_months": rng.choice([36, 36, 60])})
    by_dom = {}
    for b in base:
        by_dom.setdefault(b["customer_domain"], []).append(b)

    reqs, log = [], []
    t0 = datetime(2026, 7, 6, 8, 0)
    for i in range(480):
        dom = rng.choice(list(CUSTOMERS))
        fr = rng.random() < (0.55 if dom.endswith(".qc.ca") or dom.endswith(".ca") else 0.12)
        kind = rng.choices(["rma", "non_rma", "safety"], [83, 13, 4])[0]
        cat, serials, own, key = "", [], True, ""
        units = 1
        if kind == "non_rma":
            opts = NON_RMA_FR if fr else NON_RMA_EN
            k = rng.randrange(len(opts))
            key = f"NON_RMA|{'fr' if fr else 'en'}|{k}|{len(opts) - 1}"
            body = opts[k].format(n=rng.randint(10, 9999), m=rng.choice(MODELS))
            subject = rng.choice(["Question", "Order", "Facture" if fr else "Invoice", "Soumission" if fr else "Quote"])
        else:
            cat = rng.choice(list(CATEGORY_EN)) if kind == "rma" else "PSU"
            owned = by_dom[dom]
            if rng.random() < 0.07:                                    # serial of another customer
                units_list = [rng.choice([b for b in base if b["customer_domain"] != dom])]
                own = False
            else:
                units = 2 if rng.random() < 0.08 else 1
                units_list = rng.sample(owned, units)
            serials = [u["serial"] for u in units_list]
            if rng.random() < 0.10:                                     # forgot the serial
                serials_in_text = []
            else:
                serials_in_text = serials
            opts = (SAFETY_FR if fr else SAFETY_EN) if kind == "safety" else (CATEGORY_FR if fr else CATEGORY_EN)[cat]
            k = rng.randrange(len(opts))
            key = f"{'SAFETY' if kind == 'safety' else cat}|{'fr' if fr else 'en'}|{k}|{len(opts) - 1}"
            symptom = opts[k].format(u=rng.randint(0, 7))
            sers = ", ".join(s.lower() if rng.random() < 0.15 else s for s in serials_in_text)
            if fr:
                body = (f"Bonjour, {symptom}. " + (f"Numéro(s) de série : {sers}. " if sers else "")
                        + rng.choice(["Pouvez-vous ouvrir un RMA?", "Merci de nous envoyer un remplacement.", "Urgent svp."]))
                subject = rng.choice(["RMA", "Panne serveur", "Retour sous garantie", "Problème matériel"])
            else:
                body = (f"Hi team, {symptom}. " + (f"Serial: {sers}. " if sers else "")
                        + rng.choice(["Please open an RMA.", "Can we get an advance replacement?", "Need this fixed asap.",
                                      "Let me know next steps."]))
                subject = rng.choice(["RMA request", "Hardware failure", "Warranty claim", "Server down", "help"])
            if rng.random() < 0.1:
                body = body.lower()
        received = t0 + timedelta(minutes=rng.randint(0, 60 * 24 * 90))
        sender = rng.choice(["ops", "it", "sre", "infra", "j.tremblay", "m.chen", "a.roy"]) + "@" + dom
        reqs.append({"request_id": f"R{5000 + i}", "received_at": received.isoformat(timespec="minutes"),
                     "from": sender, "subject": subject, "body": body, "language": "fr" if fr else "en",
                     "true_is_rma": kind != "non_rma", "true_category": cat, "true_safety": kind == "safety",
                     "true_serials": " ".join(serials), "serial_in_text": bool(kind != "non_rma" and serials_in_text),
                     "true_owned": own, "phrase_key": key})

        # How the manual desk handled it (the "before" picture)
        triage_h = rng.lognormvariate(1.6, 0.6)                         # hours until someone reads and triages
        need_info = kind != "non_rma" and (not serials_in_text or rng.random() < 0.12)
        info_wait_h = rng.lognormvariate(3.1, 0.5) if need_info else 0
        entry_h = rng.lognormvariate(0.9, 0.5) if kind != "non_rma" else 0
        log.append({"request_id": f"R{5000 + i}", "triage_hours": round(triage_h, 2),
                    "info_request_sent": need_info, "info_wait_hours": round(info_wait_h, 2),
                    "erp_entry_hours": round(entry_h, 2),
                    "cycle_hours": round(triage_h + info_wait_h + entry_h, 2) if kind != "non_rma" else "",
                    "miscategorized": kind == "rma" and rng.random() < 0.09,
                    "warranty_check_error": kind == "rma" and rng.random() < 0.04,
                    "safety_escalated_hours": round(triage_h, 2) if kind == "safety" else ""})

    for name, rows in [("installed_base", base), ("requests", reqs), ("baseline_log", log)]:
        with open(OUT / f"{name}.csv", "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    print(f"{len(base)} servers, {len(reqs)} requests ({sum(r['language'] == 'fr' for r in reqs)} in French)")


if __name__ == "__main__":
    main()

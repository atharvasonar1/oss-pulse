# Labeling Methodology

## 1. Disruption Window Definition

Each positive example is labeled with a 90-day window ending near the date when a disruption became public.  
The working assumption is that warning signals appear before broad public recognition.  
For each positive row in `docs/labeled_events.csv`, `disruption_start_date` and `disruption_end_date` define that pre-event observation window.

## 2. Healthy Window Selection

Healthy examples use non-overlapping 90-day windows from repositories in `docs/project-list.md` during periods with no major publicly documented disruption of the selected type.  
Windows are distributed across different years and ecosystems to increase diversity in release cadence, contributor patterns, and issue activity.  
Healthy rows are labeled `0` and include multiple repos such as `prometheus/prometheus`, `cli/cli`, and `grafana/grafana`.

## 3. Positive Case Rationale

The 15 positive cases were selected because they represent known disruption modes relevant to open source dependency risk:

- `hashicorp/terraform` (2023): license transition pressure and ecosystem trust shift.
- `curl/curl` (2014): dependency risk signals from OpenSSL before Heartbleed disclosure.
- `log4j/log4j` (2021): pre-incident security stress before Log4Shell became public.
- `openssl/openssl` (2014): maintainer load and security process stress before Heartbleed.
- `docker/docker` (2017): contributor and governance turbulence around the Moby split.
- `libressl-portable/libressl` (2014): fork event tied to OpenSSL trust and governance crisis.
- `ansible/ansible` (2019): community transition tension around collections restructuring.
- `kubernetes/kubernetes` (2015): early-stage contributor concentration risk before maturation.
- `struts/struts` (2017): pre-vulnerability warning posture concerns.
- `nicowillis/colors` (2022): maintainer sabotage style release incident signals.
- `nicowillis/faker` (2022): maintainer sabotage style release incident signals.
- `dominictarr/event-stream` (2018): supply-chain backdoor insertion case.
- `zloirock/core-js` (2020): maintainer burnout and sustainability stress signals.
- `babel/babel` (2020): funding strain and maintainer overload risk.
- `left-pad/left-pad` (2016): package removal shock and ecosystem fragility.

## 4. Dataset Limitations

- Labels are based on historical public narratives and are not perfect causal ground truth.
- Some windows reflect ecosystem-level stress (for example dependency crises) rather than direct repository faults.
- Start and end dates are approximate and may not match the exact onset of hidden risk signals.
- Negative windows can still contain weak risk signals that did not materialize into major incidents.
- Repository selection is biased toward infrastructure-heavy projects relevant to this system.

## 5. Class Imbalance Handling in Training

The dataset is intentionally imbalanced toward healthy windows. During model training:

- Use class weighting (for example `class_weight='balanced'`) for linear models.
- Use stratified train/test splits to preserve positive/negative ratios.
- Track ROC-AUC and F1 together to avoid accuracy-only bias.
- Tune decision thresholds for recall/precision tradeoffs.
- Revisit calibration as more labeled disruption cases are added.

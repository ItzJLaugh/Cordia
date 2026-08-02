/* The certification instruments.

   Deliberately NOT merged into curriculum-tiers.js: TIERS is consumed by
   tier.html, which treats every entry as a learner tier. Calibration is not
   a learner tier — it is the human rating instrument whose output realigns
   scoring — so it lives here and is composed in only where it belongs. */

const CERT_INSTRUMENTS = [
  {
    id: 'aie', kind: 'exam', code: 'CordiaAIE', name: 'AI Employee',
    badge: 'assets/img/badge-aie.svg',
    href: 'exam.html?cert=aie',
    blurb: 'Safe baseline use. Can state intent, spot a bad output, and knows what not to hand over.',
    items: 12, live: true,
  },
  {
    id: 'caie', kind: 'exam', code: 'CordiaCAIE', name: 'Certified AI Employee',
    badge: 'assets/img/badge-caie.svg',
    href: 'exam.html?cert=caie',
    blurb: 'Transmissible specification. Can write intent another person could execute from.',
    items: null, live: false,
  },
  {
    id: 'caaie', kind: 'exam', code: 'CordiaCAAIE', name: 'Certified Advanced AI Employee',
    badge: 'assets/img/badge-caaie.svg',
    href: 'exam.html?cert=caaie',
    blurb: 'Stance and accountability. Can own a system they did not personally execute.',
    items: null, live: false,
  },
  {
    id: 'calib', kind: 'calibration', code: 'Calibration', name: '77-item rater study',
    badge: 'assets/img/badge-calib.svg',
    href: 'rate.html',
    blurb: 'Not a learner exam. Two humans independently grade the same real answers on the ' +
           '0–3 rubric; their agreement (Cohen’s κ) is what tells us whether the ' +
           'automated scorer can be trusted.',
    items: 77, live: true, restricted: true,
  },
];

/* Cordia cognitive categories.

   The 15 domain tracks grouped by the KIND OF THINKING each trains, rather
   than by industry sector. Grouping was derived from each track's own `cog`
   field in curriculum-tracks-*.js, not invented.

   Additive by design: curriculum-tracks-a|b|c.js are also loaded by
   course.html and environment.html and must not change. */

const CATEGORIES = [
  {
    id: 'uncertainty',
    name: 'Uncertainty & consequence',
    sub: 'Where the cost of being wrong is not symmetric.',
    tracks: ['healthcare', 'frontline', 'energy'],
    icons: ['pulse', 'fork', 'weigh'],
  },
  {
    id: 'reconciliation',
    name: 'Reconciliation & audit',
    sub: 'Tracking state against a plan, and catching the drift.',
    tracks: ['finance', 'supplychain', 'construction'],
    icons: ['ledger', 'funnel', 'cycle'],
  },
  {
    id: 'precedent',
    name: 'Precedent & legitimacy',
    sub: 'Where how a decision was reached matters as much as the decision.',
    tracks: ['legal', 'hr', 'public'],
    icons: ['strata', 'pillar', 'circle'],
  },
  {
    id: 'decomposition',
    name: 'Decomposition & systems',
    sub: 'Breaking a problem apart without losing how the parts couple.',
    tracks: ['software', 'engineering', 'trades'],
    icons: ['nest', 'systems', 'tree'],
  },
  {
    id: 'minds',
    name: 'Modeling other minds',
    sub: 'Reasoning about what someone else knows, wants, or will misread.',
    tracks: ['marketing', 'sales', 'education'],
    icons: ['mind', 'dialogue', 'ripple'],
  },
];

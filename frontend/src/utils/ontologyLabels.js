// أسماء عربية للأنواع التي يولّدها المحرّك.
// المفتاح الإنجليزي يبقى كما هو في البيانات والشبكة (مفتاح تقني)، والواجهة
// تعرض العربي فقط. الأنواع التي يأتي معها label_ar من الخادم تُقدَّم عليه.

export const ENTITY_TYPE_AR = {
  PoliticalLeader: 'قائد سياسي',
  MilitaryLeader: 'قائد عسكري',
  Historian: 'مؤرخ',
  Citizen: 'مواطن',
  Soldier: 'جندي',
  MediaOutlet: 'وسيلة إعلام',
  Psychologist: 'عالم نفس',
  Person: 'شخص',
  GovernmentAgency: 'جهة حكومية',
  Organization: 'منظمة',
  Student: 'طالب',
  Teacher: 'معلّم',
  Professor: 'أستاذ جامعي',
  Doctor: 'طبيب',
  Nurse: 'ممرض',
  Engineer: 'مهندس',
  Merchant: 'تاجر',
  Trader: 'تاجر',
  Driver: 'سائق',
  Farmer: 'مزارع',
  Worker: 'عامل',
  Employee: 'موظف',
  Journalist: 'صحافي',
  Reporter: 'مراسل',
  Activist: 'ناشط',
  Politician: 'سياسي',
  Official: 'مسؤول',
  Judge: 'قاضٍ',
  Lawyer: 'محامٍ',
  Researcher: 'باحث',
  Economist: 'خبير اقتصادي',
  Analyst: 'محلل',
  Bank: 'بنك',
  Company: 'شركة',
  Business: 'منشأة تجارية',
  Ngo: 'منظمة مجتمع مدني',
  University: 'جامعة',
  School: 'مدرسة',
  Hospital: 'مستشفى',
  Ministry: 'وزارة',
  Court: 'محكمة',
  Police: 'شرطة',
  Army: 'جيش',
  Party: 'حزب',
  Union: 'اتحاد نقابي',
  Media: 'إعلام',
  NewsAgency: 'وكالة أنباء',
  SocialMediaPlatform: 'منصّة تواصل',
  Community: 'مجموعة محلية',
  Tribe: 'قبيلة',
  ReligiousLeader: 'قائد ديني',
  Artist: 'فنان',
  Athlete: 'رياضي',
  Influencer: 'مؤثر',
  Customer: 'عميل',
  Consumer: 'مستهلك',
  Patient: 'مريض',
  Refugee: 'لاجئ',
  DisplacedPerson: 'نازح',
  Family: 'أسرة',
  Neighborhood: 'حي',
  Product: 'منتج',
  Currency: 'عملة',
  Service: 'خدمة',
  Rider: 'راكب',
  Passenger: 'راكب',
  Driver: 'سائق',
  TaxiDriver: 'سائق تاكسي',
  RikshaDriver: 'سائق ركشة',
  TukTukDriver: 'سائق ركشة',
  VehicleOwner: 'صاحب مركبة',
  DriverAssociation: 'جمعية سائقين',
  Customer: 'عميل',
  Platform: 'منصّة',
  App: 'تطبيق',
  Regulator: 'جهة تنظيم',
  Association: 'جمعية'
}

export const RELATION_TYPE_AR = {
  RESPONDS_TO: 'يردّ على',
  MAKES_STATEMENT: 'يصرّح',
  WORKS_FOR: 'يعمل لدى',
  OPPOSES: 'يعارض',
  SUPPORTS: 'يدعم',
  REPORTS_ON: 'يغطّي',
  AFFILIATED_WITH: 'منتسب إلى',
  ANALYZES: 'يحلّل',
  PART_OF: 'جزء من',
  LOCATED_IN: 'يقع في',
  LEADS: 'يقود',
  MEMBER_OF: 'عضو في',
  CRITICIZES: 'ينتقد',
  COLLABORATES_WITH: 'يتعاون مع',
  COMPETES_WITH: 'ينافس',
  OWNS: 'يملك',
  FUNDS: 'يموّل',
  REGULATES: 'ينظّم',
  EMPLOYS: 'يوظّف',
  ATTENDS: 'يحضر',
  PRODUCES: 'ينتج',
  SELLS: 'يبيع',
  BUYS: 'يشتري',
  CONSULTS: 'يستشير',
  REPLACES: 'يستبدل',
  INFLUENCES: 'يؤثر في',
  USES: 'يستخدم',
  TEACHES: 'يدرّس',
  STUDIES_AT: 'يدرس في',
  TREATS: 'يعالج',
  RELATED_TO: 'مرتبط بـ',
  REQUESTS_RIDE: 'يطلب مشوارًا',
  ACCEPTS_RIDE: 'يقبل المشوار',
  EMPLOYED_BY: 'يعمل لدى',
  MEMBER_OF: 'عضو في',
  OWNS_VEHICLE: 'يملك مركبة',
  PAYS_COMMISSION: 'يدفع عمولة',
  REGULATED_BY: 'تنظّمه جهة',
  COMPLAINS_ABOUT: 'يشتكي من',
  SETS_PRICE: 'يحدّد السعر',
  USES_PLATFORM: 'يستخدم منصّة'
}

// أسماء عربية تأتي من الخادم (label_ar) أو تُتعلَّم من مخطط المشروع لحظة فتحه.
// الهدف: حتى رؤوس الشبكة والمخطط تستعمل العربي نفسه الذي في أعلى الصفحة.
const dynamicLabels = {
  entities: {},
  relations: {}
}

export function registerOntology(ontology) {
  if (!ontology || typeof ontology !== 'object') return
  for (const item of (ontology.entity_types || [])) {
    if (item && item.name && (item.label_ar || '').trim()) {
      dynamicLabels.entities[item.name] = item.label_ar.trim()
    }
  }
  for (const item of (ontology.edge_types || [])) {
    if (item && item.name && (item.label_ar || '').trim()) {
      dynamicLabels.relations[item.name] = item.label_ar.trim()
    }
  }
}

function normalizeKey(value) {
  return String(value || '')
    .trim()
    .replace(/[\s-]+/g, '_')
}

// مفتاح عربي من اسم إنجليزي قد يأتي PascalCase أو UPPER_SNAKE_CASE
function lookup(map, name) {
  if (!name) return ''
  const raw = String(name).trim()
  if (map[raw]) return map[raw]
  const snake = normalizeKey(raw).toUpperCase()
  if (map[snake]) return map[snake]
  const compact = raw.replace(/[_\s]/g, '').toLowerCase()
  for (const key of Object.keys(map)) {
    if (key.replace(/[_\s]/g, '').toLowerCase() === compact) return map[key]
  }
  return ''
}

/** الاسم العربي لنوع كيان: label_ar من الخادم ← القاموس ← الاسم الأصلي */
export function entityTypeLabel(item) {
  if (typeof item === 'string') {
    return lookup(ENTITY_TYPE_AR, item) || dynamicLabels.entities[item] || item
  }
  if (!item) return ''
  const fromServer = (item.label_ar || item.labelAr || '').trim()
  if (fromServer) return fromServer
  return lookup(ENTITY_TYPE_AR, item.name) ||
    dynamicLabels.entities[item.name] || item.name || ''
}

/** الاسم العربي لنوع علاقة */
export function relationTypeLabel(item) {
  if (typeof item === 'string') {
    return lookup(RELATION_TYPE_AR, item) || dynamicLabels.relations[item] || item.replace(/_/g, ' ')
  }
  if (!item) return ''
  const fromServer = (item.label_ar || item.labelAr || '').trim()
  if (fromServer) return fromServer
  return lookup(RELATION_TYPE_AR, item.name) ||
    dynamicLabels.relations[item.name] || String(item.name || '').replace(/_/g, ' ')
}

/** نص إنجليزي يبقى للعرض الثانوي (مفتاح تقني صغير تحت العربي) */
export function technicalName(item) {
  if (typeof item === 'string') return item
  return (item && item.name) || ''
}

const CATEGORY_COLORS:Record<string,string>={
  income:'#2E7D32',
  salary:'#388E3C',
  refunds:'#43A047',
  housing:'#6D4C41',
  groceries:'#EF6C00',
  restaurants:'#D84315',
  transport:'#1565C0',
  vehicle:'#455A64',
  utilities:'#F9A825',
  telecom:'#00838F',
  insurance:'#5E35B1',
  health:'#C62828',
  personal_care:'#AD1457',
  education:'#3949AB',
  family:'#8E24AA',
  pets:'#7B1FA2',
  sports:'#00897B',
  leisure:'#EC407A',
  technology:'#546E7A',
  shopping:'#F4511E',
  subscriptions:'#7E57C2',
  travel:'#039BE5',
  taxes:'#757575',
  bank_fees:'#8D6E63',
  debt:'#B71C1C',
  donations:'#C2185B',
  investments:'#00695C',
  savings:'#2E7D32',
  transfers:'#78909C',
  other:'#9E9E9E',
};

const FALLBACK_COLORS=[
  '#3367D6','#8E44AD','#D35400','#2E8B57','#C0392B',
  '#2874A6','#A04000','#117864','#884EA0','#566573',
];

export function categoryColor(systemKey:string,index=0):string{
  const direct=CATEGORY_COLORS[systemKey];
  if(direct)return direct;
  let hash=0;
  for(let i=0;i<systemKey.length;i++)hash=(hash*31+systemKey.charCodeAt(i))>>>0;
  return FALLBACK_COLORS[(hash+index)%FALLBACK_COLORS.length];
}

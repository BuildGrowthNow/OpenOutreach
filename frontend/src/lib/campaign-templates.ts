export interface WaTemplate {
  id: string;
  label: string;
  description: string;
  message: string;
}

export const WA_MESSAGE_TEMPLATES: WaTemplate[] = [
  {
    id: "business-confirm",
    label: "Business owner",
    description: "For local/Maps leads. Identity + signals you have a question (not a pitch).",
    message: "You run {company}, right? Quick question about how you handle new customers.",
  },
  {
    id: "corporate-area",
    label: "Corporate contact",
    description: "For LinkedIn leads. Replace [area] with the relevant function (e.g. 'sales ops', 'hiring').",
    message: "You handle [area] at {company}, right? Quick question.",
  },
  {
    id: "name-role",
    label: "Role check",
    description: "When you know their name. Replace [role] with the actual title.",
    message: "Hey {first_name} — you're the [role] at {company}, right? Quick question.",
  },
  {
    id: "referral",
    label: "Referral",
    description: "Someone gave you their number. Replace [Name] with the referrer's name.",
    message: "[Name] mentioned I should reach out. You're at {company}, right?",
  },
];

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
    description: "For local/Maps leads. Confirms the business name.",
    message: "You run {company}, right?",
  },
  {
    id: "corporate-area",
    label: "Corporate contact",
    description: "For LinkedIn leads. Confirms company + asks who owns the area.",
    message: "You're at {company} — you handle [area], right?",
  },
  {
    id: "name-role",
    label: "Role check",
    description: "When you know their name. Replace [role] with the actual title.",
    message: "Hey {first_name} — you're the [role] there, right?",
  },
  {
    id: "referral",
    label: "Referral",
    description: "Someone gave you their number. Replace [Name] with the referrer.",
    message: "[Name] mentioned I should reach out — you work at {company}, right?",
  },
];

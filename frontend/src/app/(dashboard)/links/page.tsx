import { redirect } from "next/navigation";

/** Link assets are managed from a campaign sequence, where attribution scope is explicit. */
export default function LinksPage() {
  redirect("/campaigns");
}

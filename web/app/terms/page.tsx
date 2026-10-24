import type { Metadata } from "next";
import { CONTACT_EMAIL, LegalLayout } from "@/components/LegalLayout";

export const metadata: Metadata = {
  title: "Terms of use · Job Agent Hub",
  description: "The rules for using Job Agent Hub.",
};

export default function TermsPage() {
  return (
    <LegalLayout title="Terms of use" updated="24 October 2026">
      <p>
        Job Agent Hub is a personal project shared with a small group of people. By using it you agree to these terms.
      </p>

      <h2>What the app does, and what it doesn&apos;t</h2>
      <p>
        The app drafts resumes and emails with AI and can send emails from your Gmail account, but only after you approve them. AI output can be
        wrong or incomplete. You are responsible for checking every resume and message before you approve it.
      </p>

      <h2>Your content</h2>
      <p>
        You are responsible for the material you upload or send through the app, including your resume and job postings. Only use it if you have
        the right to.
      </p>

      <h2>Acceptable use</h2>
      <ul>
        <li>Don&apos;t use the app to send spam, misleading applications, or anything that breaks the law.</li>
        <li>Don&apos;t try to access other people&apos;s accounts or data, or to disrupt the service.</li>
      </ul>

      <h2>No warranty</h2>
      <p>
        The app is provided &quot;as is&quot;, without warranties of any kind. The owner isn&apos;t liable for missed opportunities, lost data, or emails sent
        on your behalf that you approved.
      </p>

      <h2>Stopping</h2>
      <p>
        You can stop using the app at any time, disconnect Gmail in Settings, and ask for your account to be deleted. The owner may suspend
        accounts that break these terms or the Google API Services User Data Policy.
      </p>

      <h2>Changes and contact</h2>
      <p>
        These terms may be updated; the date at the top shows the latest version. Questions:{" "}
        <a href={`mailto:${CONTACT_EMAIL}`} className="text-accent underline">{CONTACT_EMAIL}</a>.
      </p>
    </LegalLayout>
  );
}

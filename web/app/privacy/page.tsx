import type { Metadata } from "next";
import { CONTACT_EMAIL, LegalLayout } from "@/components/LegalLayout";

export const metadata: Metadata = {
  title: "Privacy policy · Job Agent Hub",
  description: "What Job Agent Hub stores, who processes it, and how to delete it.",
};

export default function PrivacyPage() {
  return (
    <LegalLayout title="Privacy policy" updated="24 October 2026">
      <p>
        This policy explains what Job Agent Hub (the &quot;app&quot;) collects, why, and who processes it. The app is run by the owner whose contact address
        is at the bottom of this page.
      </p>

      <h2>What we store</h2>
      <ul>
        <li>
          <strong>Account:</strong> your email address and a password stored only as a bcrypt hash, never in readable form.
        </li>
        <li>
          <strong>Your resume:</strong> the file you upload and the structured text extracted from it.
        </li>
        <li>
          <strong>Jobs you add:</strong> the posting text or screenshot, and the company, role and keywords the app extracted from it.
        </li>
        <li>
          <strong>Generated material:</strong> tailored resumes (PDF), email drafts, and the activity log for each job.
        </li>
        <li>
          <strong>Gmail connection:</strong> the access token Google gives the app, stored encrypted, plus the connected Gmail address.
        </li>
      </ul>

      <h2>Google user data</h2>
      <p>
        The app uses Google user data only to send the emails you approve, from the Gmail address you connected. It does not read, search, list,
        store or share the contents of your mailbox. Google user data is not sold, used for advertising, or used to train AI models.
      </p>
      <p>
        Job Agent Hub&apos;s use and transfer of information received from Google APIs adheres to the{" "}
        <a href="https://developers.google.com/terms/api-services-user-data-policy" className="text-accent underline" rel="noreferrer" target="_blank">
          Google API Services User Data Policy
        </a>
        , including the Limited Use requirements.
      </p>

      <h2>Who processes your data</h2>
      <ul>
        <li>
          <strong>Supabase:</strong> database and file storage.
        </li>
        <li>
          <strong>Render:</strong> runs the backend that processes your jobs.
        </li>
        <li>
          <strong>Vercel:</strong> serves the website.
        </li>
        <li>
          <strong>Google Gemini API:</strong> reads your resume and the job text to write tailored content and drafts. On Google&apos;s free tier, Google
          may use these requests to improve its products, so avoid submitting information you don&apos;t want shared that way.
        </li>
        <li>
          <strong>Google (Gmail):</strong> sends the emails you approve.
        </li>
      </ul>

      <h2>How long we keep it, and how to delete it</h2>
      <p>
        Your data is kept until you delete it. You can disconnect Gmail in Settings at any time, and you can revoke the app&apos;s access in your
        Google Account under <em>Security → Third-party access</em> (myaccount.google.com/permissions). To delete your account and all of its data,
        email {CONTACT_EMAIL} from the address you registered with, and it will be removed.
      </p>

      <h2>Security</h2>
      <p>
        Passwords are hashed, tokens and session data are encrypted, and sign-in sessions use secure, HTTP-only cookies. No method of storage is
        perfectly secure, so please use a strong, unique password.
      </p>

      <h2>Contact</h2>
      <p>
        Questions about this policy: <a href={`mailto:${CONTACT_EMAIL}`} className="text-accent underline">{CONTACT_EMAIL}</a>.
      </p>
    </LegalLayout>
  );
}

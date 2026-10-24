import type { Metadata } from "next";
import Link from "next/link";
import { LegalLayout } from "@/components/LegalLayout";

export const metadata: Metadata = {
  title: "About · Job Agent Hub",
  description: "Job Agent Hub tailors your resume to a job, scores it, and drafts your application email. Nothing is sent without your approval.",
};

export default function AboutPage() {
  return (
    <LegalLayout title="Job Agent Hub">
      <p>
        Job Agent Hub helps a job seeker apply to roles faster and with less guesswork. You paste a job posting or upload a screenshot of it, and
        the app does the groundwork:
      </p>
      <ul>
        <li>reads the posting and pulls out the company, role and key skills,</li>
        <li>tailors your resume to that job, using only the experience you already have,</li>
        <li>scores the resume against the posting&apos;s keywords, so you can see the gaps,</li>
        <li>looks for a hiring contact on the company&apos;s own website,</li>
        <li>drafts an application email with your tailored resume attached.</li>
      </ul>

      <h2>You stay in control</h2>
      <p>
        Nothing is sent automatically. You review each email and click <strong>Approve</strong> before it leaves your account. You can edit or
        stop any job at any time.
      </p>

      <h2>Gmail permission</h2>
      <p>
        To send approved emails from your own Gmail address, the app asks Google for one permission: <em>send email on your behalf</em>. It never
        reads, lists or stores the contents of your mailbox.
      </p>

      <h2>More</h2>
      <p>
        Read the <Link href="/privacy" className="text-accent underline">privacy policy</Link> to see what data is kept and why, and the{" "}
        <Link href="/terms" className="text-accent underline">terms of use</Link>. Questions? Email{" "}
        <a href="mailto:balujaldu25@gmail.com" className="text-accent underline">balujaldu25@gmail.com</a>.
      </p>
      <p>
        <Link href="/login" className="btn-primary">
          Sign in
        </Link>
      </p>
    </LegalLayout>
  );
}

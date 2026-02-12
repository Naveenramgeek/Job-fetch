export interface Contact {
  name: string | null;
  /** Professional title (e.g. Software Engineer, Sr DevOps Engineer). Used to fetch relevant jobs. */
  title: string | null;
  email: string | null;
  phone: string | null;
  linkedin: string | null;
  github: string | null;
  location: string | null;
}

export interface ExperienceItem {
  title: string | null;
  company: string | null;
  location: string | null;
  duration: string | null;
  start: string | null;
  end: string | null;
  bullets: string[];
}

export interface EducationItem {
  degree: string | null;
  institution: string | null;
  location: string | null;
  duration: string | null;
  start: string | null;
  end: string | null;
  graduation: string | null;
  gpa: string | null;
}

export interface ProjectItem {
  name: string | null;
  bullets: string[];
  link: string | null;
}

export interface OtherBlock {
  heading: string | null;
  source_section: string | null;
  reason: string;
  text: string;
}

/** A single certification: text (name/description) and optional certificate URL. */
export interface CertificationItem {
  text: string;
  link?: string | null;
}

export interface CustomSection {
  /** Section name shown as heading */
  title: string;
  /** Optional title / subtitle for the section */
  link?: string | null;
  /** Main body / description */
  content: string;
}

export interface StructuredResume {
  contact: Contact;
  summary: string | null;
  experience: ExperienceItem[];
  projects: ProjectItem[];
  education: EducationItem[];
  skills: Record<string, string[]>;
  certifications: CertificationItem[];
  other: OtherBlock[];
  custom_sections?: CustomSection[];
}

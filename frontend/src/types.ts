// Shared API shapes, per SPEC.md section 4.

export type Plan = 'Free' | 'Premium' | 'Pro';
export type ThemePref = 'light' | 'dark' | 'device';

export interface Tender {
  tender_id: number;
  ref_no?: string | null;
  app_id?: number | null;
  title?: string | null;
  description?: string | null;
  status?: string | null;
  proc_nature?: string | null;
  proc_type?: string | null;
  event_type?: string | null;
  invitation_for?: string | null;
  method?: string | null;
  budget_type?: string | null;
  source_of_funds?: string | null;
  ministry?: string | null;
  division?: string | null;
  organisation?: string | null;
  department?: string | null;
  procuring_entity?: string | null;
  procuring_entity_code?: string | null;
  district?: string | null;
  project_code?: string | null;
  project_name?: string | null;
  package_no?: string | null;
  package_description?: string | null;
  category?: string | null;
  publish_dt?: string | null;
  doc_last_selling_dt?: string | null;
  close_dt?: string | null;
  opening_dt?: string | null;
  document_price_bdt?: number | null;
  emd_bdt?: number | null;
  eligibility_text?: string | null;
  // Computed by the backend (SPEC section 10).
  work_type?: string | null;
  departments?: string[];
  computed_division?: string | null;
  status_bucket?: 'active' | 'closing_soon' | 'closed';
}

export interface TenderListResponse {
  tenders: Tender[];
  total: number;
  work_type_counts: Record<string, number>;
  department_counts: Record<string, number>;
  districts: string[];
  divisions: string[];
  methods: string[];
}

export interface FetchRun {
  id: number;
  started_at?: string | null;
  finished_at?: string | null;
  source?: string | null;
  tenders_found?: number;
  tenders_new?: number;
  tenders_updated?: number;
  details_fetched?: number;
  errors?: number;
  notes?: string | null;
}

export interface Stats {
  total: number;
  open_now: number;
  last_run: FetchRun | null;
}

export interface User {
  id: number;
  name: string;
  email: string;
  plan: Plan;
  is_admin: boolean;
}

export interface Me extends User {
  has_profile: boolean;
  pending_payment_plan: string | null;
}

export interface AuthResponse {
  user: User;
  token: string;
}

export interface SimilarWork {
  title: string;
  value_bdt?: number | null;
  category?: string | null;
}

export interface CompanyProfile {
  id?: number;
  user_id?: number;
  company_name: string;
  trade_license_no?: string | null;
  tin_no?: string | null;
  incorporation_year?: number | null;
  annual_turnover_bdt?: number | null;
  liquid_assets_bdt?: number | null;
  categories?: string | null;
  districts?: string | null;
  similar_works?: SimilarWork[];
  key_personnel?: string | null;
  equipment?: string | null;
  about?: string | null;
  updated_at?: string | null;
}

export interface DocumentItem {
  id: number;
  doc_type: string;
  file_name: string;
  mime_type?: string | null;
  size_bytes?: number | null;
  status?: string | null;
  uploaded_at?: string | null;
}

export type BidStage =
  | 'Watching'
  | 'Shortlisted'
  | 'Preparing'
  | 'Submitted'
  | 'Won'
  | 'Lost';

export interface Favourite {
  tender_id: number;
  stage: BidStage;
  tender: Tender;
}

export interface FavouritesResponse {
  favourites: Favourite[];
  favourite_ids: number[];
}

export interface AlertPrefs {
  keywords?: string | null;
  categories?: string | null;
  districts?: string | null;
  organisations?: string | null;
}

export interface AlertsResponse {
  prefs: AlertPrefs | null;
  matches: Tender[];
}

export interface JvPoster {
  name?: string | null;
  company_name?: string | null;
  categories?: string | null;
  turnover?: number | null;
}

export interface JvPost {
  id: number;
  user_id?: number;
  tender_id?: number | null;
  tender_title?: string | null;
  title: string;
  need_description: string;
  looking_for?: string | null;
  share_offered?: string | null;
  status?: string;
  created_at?: string | null;
  poster?: JvPoster | null;
  interest_count?: number;
  room_id?: number | null;
}

export interface JvRoom {
  id: number;
  post_id: number;
  title?: string | null;
  created_at?: string | null;
}

export interface JvMessage {
  id: number;
  room_id: number;
  user_id?: number;
  sender_name?: string | null;
  body: string;
  created_at?: string | null;
}

export interface RoomMessagesResponse {
  messages: JvMessage[];
  locked?: boolean;
}

export interface PaymentSubmission {
  id: number;
  user_id?: number;
  plan: Plan;
  method: string;
  transaction_id: string;
  sender_number?: string | null;
  amount_bdt?: number | null;
  status: 'Pending' | 'Approved' | 'Rejected';
  submitted_at?: string | null;
  reviewed_at?: string | null;
  review_note?: string | null;
  // Admin overview joins.
  user_name?: string | null;
  user_email?: string | null;
  name?: string | null;
  email?: string | null;
}

export interface ConsultingRequest {
  id: number;
  user_id?: number;
  tender_id?: number | null;
  tender_title?: string | null;
  topic: string;
  message: string;
  status: 'Open' | 'Answered';
  reply?: string | null;
  replied_at?: string | null;
  created_at?: string | null;
  // Admin overview joins.
  user_name?: string | null;
  user_email?: string | null;
  name?: string | null;
  email?: string | null;
  company_name?: string | null;
  plan?: string | null;
}

export interface AdminUserRow {
  id: number;
  name: string;
  email: string;
  is_admin: boolean;
  plan: Plan;
  company?: string | null;
  company_name?: string | null;
  signed_up_at?: string | null;
  created_at?: string | null;
  counts?: {
    favourites?: number;
    documents?: number;
    jv_posts?: number;
    consulting_requests?: number;
  };
  has_alert_prefs?: boolean;
}

export interface AdminOverview {
  totals: {
    users: number;
    premium: number;
    pro: number;
    pending_payments: number;
    open_consulting: number;
    tenders: number;
  };
  users: AdminUserRow[];
  payments: PaymentSubmission[];
  consulting: ConsultingRequest[];
}

export interface EligibilityCheck {
  key: string;
  status: 'pass' | 'partial' | 'fail' | 'unknown';
  points: number;
  max_points: number;
  detail: string;
}

export interface Evaluation {
  has_profile: boolean;
  score: number | null;
  verdict: string | null;
  checks: EligibilityCheck[];
  note: string;
}

export interface Summary {
  headline: string;
  scope: string;
  eligibility_points: string[];
  key_requirements: string[];
  watch_outs: string[];
}

export interface RefreshSummary {
  tenders_found?: number;
  tenders_new?: number;
  tenders_updated?: number;
  details_fetched?: number;
  errors?: number;
  [key: string]: unknown;
}

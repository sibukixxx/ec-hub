// API response types

export interface DashboardData {
  candidates: {
    pending: number;
    approved: number;
    listed: number;
  };
  orders: {
    awaiting_purchase: number;
    shipped: number;
    completed: number;
  };
  recent_profit: number;
  fx_rate: number;
  health: ServiceHealth[];
  recent_jobs: JobRun[];
}

export interface ServiceHealth {
  service_name: string;
  status: string;
  error_message: string | null;
}

export interface Candidate {
  id: number;
  title_jp: string | null;
  source_site: string;
  ebay_title: string | null;
  ebay_url: string | null;
  cost_jpy: number | null;
  ebay_price_usd: number | null;
  net_profit_jpy: number | null;
  margin_rate: number | null;
  match_score: number | null;
  match_reason: string | null;
  status: string;
}

export interface Order {
  id: number;
  ebay_order_id: string | null;
  buyer_username: string | null;
  sale_price_usd: number | null;
  actual_cost_jpy: number | null;
  net_profit_jpy: number | null;
  destination_country: string | null;
  tracking_number: string | null;
  status: string;
  ordered_at: string | null;
}

export interface ProfitForm {
  cost_jpy: number;
  ebay_price_usd: number;
  weight_g: number;
  destination: string;
}

export interface ProfitResult {
  jpy_revenue: number;
  fx_rate: number;
  jpy_cost: number;
  ebay_fee: number;
  payoneer_fee: number;
  shipping_cost: number;
  packing_cost: number;
  fx_buffer: number;
  net_profit: number;
  margin_rate: number;
}

export interface EbayItem {
  item_id: string;
  title: string | null;
  price_usd: number | null;
  price_jpy: number | null;
  condition: string | null;
  url: string | null;
  image_url: string | null;
  shipping: {
    free: boolean;
    cost: number | null;
  } | null;
}

export interface SourceCandidate extends Candidate {
  compare_match_score?: number | null;
  compare_match_reason?: string | null;
}

export interface CompareResult {
  ebay_items: EbayItem[];
  source_candidates: SourceCandidate[];
  fx_rate: number;
}

export interface Message {
  id: number;
  buyer_username: string;
  direction: 'inbound' | 'outbound';
  order_ebay_order_id: string | null;
  order_id: number | null;
  listing_sku: string | null;
  listing_id: number | null;
  candidate_item_code: string | null;
  candidate_id: number | null;
  category: string | null;
  body: string;
}

export interface ResearchRun {
  id: number;
  query: string;
  ebay_results_count: number;
  candidates_found: number;
  started_at: string | null;
  completed_at: string | null;
}

export interface ListingLimits {
  current: number;
  max: number;
  remaining: number;
}

export interface ListingPreview {
  candidate_id: number;
  title_jp: string | null;
  source_site: string;
  cost_jpy: number;
  weight_g: number;
  listing_price_usd: number;
  fx_rate: number;
  ebay_fee_jpy: number;
  payoneer_fee_jpy: number;
  shipping_cost_jpy: number;
  packing_cost_jpy: number;
  estimated_profit_jpy: number;
  sku: string;
  status: string;
}

export interface JobRun {
  id: number;
  job_name: string;
  status: string;
  items_processed: number;
  started_at: string | null;
}

export interface SchedulerStatus {
  running: boolean;
}

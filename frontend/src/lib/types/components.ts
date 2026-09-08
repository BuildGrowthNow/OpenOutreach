"use client";

import {
  LayoutDashboard,
  Activity,
  Users,
  MessageSquare,
  Link,
  Settings,
  Menu,
  X,
  LogOut,
  Sparkles,
  BarChart3,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Moon,
  Sun,
  Search,
  Filter,
  Plus,
  Download,
  Edit,
  Trash2,
  Mail,
  UserPlus,
  Phone,
  FileText,
  Database,
  Server,
  Cpu,
  HardDrive,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  MoreHorizontal,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  XCircle,
  CheckCircle,
  CircleEllipsis,
  DollarSign,
  Circle,
  Play,
  Pause,
  Network,
  Workflow,
  ArrowRight,
  Zap,
  Check,
  Handshake,
  Trophy,
  Ghost,
  Shield,
  Copy,
  Clipboard,
  Calendar,
  Briefcase,
  TrendingDown,
  ListTodo,
  BarChartBig,
  TrendingUp,
  SlidersHorizontal,
  User,
  Globe,
  Lock,
  Tag,
  Share2,
  ZoomIn,
  ZoomOut,
  Home,
  StopCircle,
  Hash,
  Type,
  Eye,
  EyeOff,
  Info,
  Save,
  Terminal,
  Bell,
  Target,
  MessageCircle,
  Inbox,
  InboxIcon,
  CreditCard,
  Loader,
  Upload,
  RotateCcw,
} from "lucide-react";

export type Icon = React.FC<React.SVGProps<SVGSVGElement>>;

export const Icons = {
  Menu,
  X,
  LogOut,
  Sparkles,
  LayoutDashboard,
  Activity,
  Users,
  MessageSquare,
  Link,
  Settings,
  BarChart3,
  Clock,
  CheckCircle2,
  AlertCircle,
  AlertTriangle,
  Bell,
  Moon,
  Sun,
  Search,
  Filter,
  Plus,
  Download,
  Edit,
  Trash2,
  Mail,
  UserPlus,
  Phone,
  FileText,
  Database,
  Server,
  Cpu,
  HardDrive,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  MoreHorizontal,
  RefreshCw,
  ChevronDown,
  ChevronUp,
  XCircle,
  CheckCircle,
  CircleEllipsis,
  DollarSign,
  Circle,
  Play,
  Pause,
  Network,
  Workflow,
  ArrowRight,
  Zap,
  Check,
  Handshake,
  Trophy,
  Ghost,
  Shield,
  Copy,
  Clipboard,
  Calendar,
  Briefcase,
  TrendingDown,
  ListTodo,
  BarChartBig,
  TrendingUp,
  SlidersHorizontal,
  User,
  Globe,
  Lock,
  Tag,
  Share2,
  ZoomIn,
  ZoomOut,
  Home,
  StopCircle,
  Hash,
  Type,
  Eye,
  EyeOff,
  Info,
  Save,
  Terminal,
  Target,
  MessageCircle,
  Inbox,
  InboxIcon,
  CreditCard,
  Loader,
  Upload,
  RotateCcw,
};

// Campaign status variants
export type CampaignStatus = "active" | "paused" | "draft";

// Deal state variants
export type DealState =
  | "DISCOVERED"
  | "QUALIFIED"
  | "READY_TO_CONNECT"
  | "PENDING"
  | "CONNECTED"
  | "COMPLETED"
  | "FAILED"
  | "NO_EMAIL"
  | "EMAIL_QUEUED"
  | "EMAIL_SENT"
  | "EMAIL_OPENED"
  | "EMAIL_REPLIED"
  | "EMAIL_BOUNCED";

// Deal outcome variants
export type DealOutcome =
  | "converted"
  | "not_interested"
  | "wrong_fit"
  | "no_budget"
  | "has_solution"
  | "bad_timing"
  | "unresponsive"
  | "unknown";

// API response types
export interface Pagination {
  page: number;
  limit: number;
  total: number;
  total_pages: number;
}

export interface CampaignStats {
  totalLeads: number;
  activeLeads: number;
  qualified: number;
  readyToConnect: number;
  pending: number;
  connected: number;
  completed: number;
  failed: number;
  noEmail: number;
  connectionsSent: number;
  connectionsAccepted: number;
  messagesSent: number;
  messagesReplied: number;
  responses: number;
  connectionAcceptRate: number;
  responseRate: number;
  conversionRate: number;
  noEmailCount?: number;
  todayConnectBudget?: number | null;
  emailQueued?: number;
  emailSent?: number;
  emailOpened?: number;
  emailReplied?: number;
  emailBounced?: number;
}

export interface Lead {
  id: string;
  publicIdentifier: string;
  linkedinUrl: string;
  name?: string;
  company?: string;
  title?: string;
  state: DealState;
  outcome?: DealOutcome;
  nextCheckPendingAt?: string;
  lastOutgoingAt?: string;
  nextFollowUpAt?: string;
  unansweredCount?: number;
  creationDate: string;
  updateDate: string;
  contactInfo?: {
    email?: string;
    apiEmail?: string;
    overlayEmail?: string;
    phoneNumbers?: string[];
  };
  phone?: string;
  activeChannel?: string;
  channelAvailability?: {
    linkedin: boolean;
    email: boolean;
    whatsapp: boolean;
  };
  messagesCount?: number;
  lastMessageAt?: string;
  notes?: string;
  notesCount?: number;
  lastNotes?: Array<{ id: string; content: string }>;
  campaignId?: string;
  campaignName?: string;
  disqualified?: boolean;
  qualificationHold?: boolean;
  qualificationReason?: string;
  connectAttempts?: number;
  emailSequenceStep?: number;
  emailSentAt?: string;
  profile?: {
    firstName?: string;
    lastName?: string;
    headline?: string;
    summary?: string;
    location?: string;
    experience?: Array<{
      company?: string;
      title?: string;
      duration?: string;
    }>;
    education?: Array<{
      school?: string;
      degree?: string;
      year?: string;
    }>;
  };
}

export interface Campaign {
  id: string;
  name: string;
  description: string;
  productPitch?: string;
  campaignObjective?: string;
  bookingLink?: string;
  searchKeywords?: string[];
  icpTitles?: string[];
  targetCompanySize?: string;
  followUpStrategy?: string;
  targetDegrees?: number[];
  isFreemium: boolean;
  ghostModeEnabled: boolean;
  velocity: number;
  cooldownMinutes: number;
  status: string;
  isPaused: boolean;
  createdAt: string;
  updatedAt: string;
  stats?: CampaignStats;
  nextActionAt?: string | null;
  channelSequence?: string[];
  channelSettings?: Record<string, unknown>;
  whatsappProfileId?: string;
}

export interface Message {
  id: string;
  dealId: string;
  leadId?: string;
  campaignId?: string;
  campaignName?: string;
  dealUrn: string;
  content: string;
  isOutgoing: boolean;
  sender: "me" | "them";
  senderName?: string;
  creationDate: string;
  recipientName: string;
  recipientUrl?: string;
  channel?: string;
  waDeliveryStatus?: string
  replyIntent?: string;
}

export interface HealthStatus {
  status: "operational" | "degraded" | "unhealthy";
  message: string;
  system: {
    timestamp: string;
    python_version?: string;
    platform: string;
    cpu_percent?: number;
    memory_percent?: number;
  };
  database: {
    connected: boolean;
    engine?: string;
    database?: string;
    error?: string;
    latency_ms?: number;
    engine_type?: string;
  };
  mongodb?: {
    connected: boolean;
    latency_ms?: number;
    database?: string;
    error?: string;
  };
  database_stats?: {
    queries: number;
    success_rate: number;
    avg_latency_ms: number;
    errors: number;
    period?: string;
    error?: string;
  };
  services: {
    database: string; // 'operational' | 'degraded'
    api: string; // 'operational' | 'degraded'
    mongodb?: string; // 'operational' | 'degraded'
    linkedin: string; // 'operational' | 'degraded'
    overall?: string;
  };
}

export interface LinkMetrics {
  id: string;
  url: string;
  shortUrl: string;
  campaignId: string;
  campaignName: string;
  clicks: number;
  uniqueVisitors: number;
  lastClickAt: string;
  createdAt: string;
}

// RateLimits interface retained for backward compatibility with legacy code
// Use SystemSettings.rate_limits for the new canonical shape (daily_connection_limit, daily_follow_up_limit, etc.)

// Daily Usage Response type for API
export interface DailyUsageResponse {
  daily_connections_sent: number;
  daily_messages_sent: number;
  daily_limit: number;
  last_reset: string;
  reset_frequency: string;
}

// LinkedIn Profile Health Status interfaces
export interface LinkedInProfileHealth {
  id: number;
  linkedinUsername: string;
  status: boolean;
  credentialsStatus: string;
  healthScore: number;
  healthStatus: string;
  needsAttention: boolean;
  lastError?: string | null;
  lastVerification?: string | null;
}

export interface LinkedInProfileHealthResponse {
  profiles: LinkedInProfileHealth[];
  count: number;
  totalProfiles: number;
  needsAttentionCount: number;
}

// Canonical campaign sequence contract (mirrors openoutreach.core.sequence_schema)
export interface SequenceMessage {
  content_mode: "ai_prompt" | "static";
  prompt?: string;
  subject?: string;
  body?: string;
  link_refs: string[];
  stop_on_reply: boolean;
  fallback_mode?: "skip" | "static" | "continue";
  fallback_body?: string;
}

export interface SequenceStep {
  id: string;
  type: "action" | "wait" | "condition" | "end";
  data: {
    label: string;
    channel: "linkedin" | "email" | "whatsapp" | "internal" | null;
    action: "connect" | "follow_up" | "send_email" | "send_whatsapp" | "notify_internal" | "internal_notification" | null;
    wait_days: number;
    wait_hours: number;
    condition?: "always" | "lead_has_email" | "lead_has_phone" | "reply_received" | "email_opened" | "email_not_opened" | "link_clicked" | "link_not_clicked";
    link_key?: string;
    link_asset_id?: string;
    observation_window_hours?: number;
    requires: string[];
    message?: SequenceMessage;
    [key: string]: unknown;
  };
  position: { x: number; y: number };
}

export interface SequenceEdge {
  id: string;
  source: string;
  target: string;
  data?: { condition?: string } & Record<string, unknown>;
  [key: string]: unknown;
}

// Campaign Template types
export interface CampaignTemplate {
  id: string | number;
  name: string;
  description?: string;
  category: string;
  channels: string[];
  sequence_schema_version: number;
  sequence_steps: SequenceStep[];
  sequence_edges: SequenceEdge[];
  campaign_defaults: Record<string, unknown>;
  link_definitions: LinkDefinition[];
  safety_defaults: Record<string, unknown>;
  visibility: "private" | "team" | "system";
  version: number;
  action_count?: number;
  approximate_duration_days?: number;
  required_data?: string[];
  // Read-only compatibility aliases for older template screens.
  product_pitch?: string;
  campaign_objective?: string;
  booking_link?: string;
  icp_titles?: string[];
  follow_up_strategy?: string;
  ghost_mode_enabled?: boolean;
  velocity?: number;
  cooldown_minutes?: number;
  is_public?: boolean;
  created_at: string;
  updated_at: string;
}

export interface CampaignTemplateCreateData {
  name: string;
  description?: string;
  category?: string;
  channels?: string[];
  sequence_schema_version?: number;
  sequence_steps?: SequenceStep[];
  sequence_edges?: SequenceEdge[];
  campaign_defaults?: Record<string, unknown>;
  link_definitions?: LinkDefinition[];
  safety_defaults?: Record<string, unknown>;
  visibility?: "private" | "team";
  product_pitch?: string;
  campaign_objective?: string;
  booking_link?: string;
  icp_titles?: string[];
  follow_up_strategy?: string;
}

export interface LinkDefinition {
  key: string;
  name: string;
  destination_mode: "campaign_booking_link" | "custom";
  default_destination_url?: string | null;
  default_utm?: Record<string, string>;
}

// LinkedIn Setup Status types
export interface LinkedInSetupStatus {
  success: boolean;
  status: {
    linkedin_profile: {
      exists: boolean;
      count: number;
      requires_attention: boolean;
    };
    linkedin_credentials: {
      exists: boolean;
      count: number;
      active_count: number;
      requires_attention: boolean;
    };
    setup_complete: boolean;
    setup_progress: {
      current: number;
      total: number;
    };
  };
}

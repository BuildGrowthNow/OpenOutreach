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
  | "NO_EMAIL";

// Deal outcome variants
export type DealOutcome =
  | "not_interested"
  | "interested"
  | "scheduled"
  | "wrong_person"
  | "no_response"
  | "other";

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
  messagesCount?: number;
  lastMessageAt?: string;
  notes?: string;
  notesCount?: number;
  lastNotes?: Array<{ id: string; content: string }>;
  campaignId?: string;
  campaignName?: string;
  disqualified?: boolean;
  connectAttempts?: number;
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
}

export interface HealthStatus {
  status: "operational" | "degraded" | "unhealthy";
  message: string;
  system: {
    timestamp: string;
    python_version: string;
    platform: string;
    cpu_percent: number;
    memory_percent: number;
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

// Campaign Template types
export interface CampaignTemplate {
  id: number;
  name: string;
  description?: string;
  product_pitch?: string;
  campaign_objective?: string;
  booking_link?: string;
  search_keywords?: string[];
  icp_titles?: string[];
  follow_up_strategy?: string;
  ghost_mode_enabled: boolean;
  velocity: number;
  cooldown_minutes: number;
  is_public: boolean;
  created_by: {
    id: number;
    username: string;
  };
  created_at: string;
  updated_at: string;
}

export interface CampaignTemplateCreateData {
  name: string;
  description?: string;
  product_pitch?: string;
  campaign_objective?: string;
  booking_link?: string;
  search_keywords?: string[];
  icp_titles?: string[];
  follow_up_strategy?: string;
  ghost_mode_enabled?: boolean;
  velocity?: number;
  cooldown_minutes?: number;
  is_public?: boolean;
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

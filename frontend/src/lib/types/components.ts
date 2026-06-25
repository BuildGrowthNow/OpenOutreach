'use client'

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
  Save
} from 'lucide-react'

export type Icon = React.FC<React.SVGProps<SVGSVGElement>>

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
  Save
}

// Campaign status variants
export type CampaignStatus = 'active' | 'paused' | 'draft'

// Deal state variants
export type DealState = 
  | 'QUALIFIED'
  | 'READY_TO_CONNECT'
  | 'PENDING'
  | 'CONNECTED'
  | 'COMPLETED'
  | 'FAILED'
  | 'NO_EMAIL'

// Deal outcome variants
export type DealOutcome = 
  | 'not_interested'
  | 'interested'
  | 'scheduled'
  | 'wrong_person'
  | 'no_response'
  | 'other'

// API response types
export interface Pagination {
  page: number
  limit: number
  total: number
  total_pages: number
}

export interface CampaignStats {
  totalLeads: number
  qualified: number
  readyToConnect: number
  pending: number
  connected: number
  completed: number
  failed: number
  noEmail: number
  messagesSent: number
  messagesReplied: number
  connectionAcceptRate: number
  responseRate: number
}

export interface Lead {
  id: string
  publicIdentifier: string
  linkedinUrl: string
  name?: string
  company?: string
  title?: string
  state: DealState
  outcome?: DealOutcome
  nextCheckPendingAt?: string
  creationDate: string
  updateDate: string
  contactInfo?: {
    email?: string
    phoneNumbers?: string[]
  }
  messagesCount?: number
  lastMessageAt?: string
  notes?: string
  disqualified?: boolean
}

export interface Campaign {
  id: string
  name: string
  description: string
  productDocs?: string
  campaignObjective?: string
  bookingLink?: string
  isFreemium: boolean
  ghostModeEnabled: boolean
  velocity: number
  cooldownMinutes: number
  status: string
  isPaused: boolean
  createdAt: string
  updatedAt: string
  stats?: CampaignStats
}

export interface Message {
  id: string
  dealId: string
  dealUrn: string
  content: string
  isOutgoing: boolean
  sender: 'me' | 'them'
  creationDate: string
  recipientName: string
  recipientUrl: string
}

export interface HealthStatus {
  status: 'operational' | 'degraded' | 'unhealthy'
  message: string
  system: {
    timestamp: string
    python_version: string
    platform: string
    cpu_percent: number
    memory_percent: number
  }
  database: {
    connected: boolean
    engine?: string
    database?: string
    error?: string
  }
  services: {
    database: string  // 'operational' | 'degraded'
    api: string       // 'operational' | 'degraded'
    linkedin: string  // 'operational' | 'degraded'
    overall?: string
  }
}

export interface LinkMetrics {
  id: string
  url: string
  shortUrl: string
  campaignId: string
  campaignName: string
  clicks: number
  uniqueVisitors: number
  lastClickAt: string
  createdAt: string
}

// RateLimits interface retained for backward compatibility with legacy code
// Use SystemSettings.rate_limits for the new canonical shape (daily_connection_limit, daily_follow_up_limit, etc.)

// Daily Usage Response type for API
export interface DailyUsageResponse {
  daily_connections_sent: number
  daily_messages_sent: number
  daily_limit: number
  last_reset: string
  reset_frequency: string
}

// LinkedIn Profile Health Status interfaces
export interface LinkedInProfileHealth {
  id: number
  linkedin_username: string
  status: boolean
  credentials_status: string
  health_score: number
  health_status: string
  needs_attention: boolean
}

export interface LinkedInProfileHealthResponse {
  profiles: LinkedInProfileHealth[]
  count: number
  total_profiles: number
  needs_attention_count: number
}

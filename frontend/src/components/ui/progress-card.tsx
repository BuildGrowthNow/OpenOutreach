import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface ProgressCardProps {
  title: string;
  value: number | string;
  subtitle?: string;
  progress?: number;
  progressColor?: 'emerald' | 'blue' | 'purple' | 'amber' | 'rose';
  trend?: {
    value: number;
    isPositive: boolean;
  };
  icon?: React.ReactNode;
}

const colorClasses = {
  emerald: 'bg-emerald-500',
  blue: 'bg-blue-500',
  purple: 'bg-purple-500',
  amber: 'bg-amber-500',
  rose: 'bg-rose-500',
};

export function ProgressCard({
  title,
  value,
  subtitle,
  progress,
  progressColor = 'blue',
  trend,
  icon,
}: ProgressCardProps) {
  return (
    <Card className="overflow-hidden hover:shadow-lg transition-shadow">
      <CardHeader className="pb-3">
        <div className="flex items-start justify-between">
          <div className="flex-1">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              {title}
            </CardTitle>
          </div>
          {icon && <div className="text-muted-foreground">{icon}</div>}
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <div className="flex items-baseline justify-between">
          <div className="text-3xl font-bold tracking-tight">{value}</div>
          {trend && (
            <div
              className={cn(
                'text-xs font-semibold',
                trend.isPositive
                  ? 'text-emerald-600 dark:text-emerald-400'
                  : 'text-rose-600 dark:text-rose-400'
              )}
            >
              {trend.isPositive ? '↑' : '↓'} {Math.abs(trend.value)}%
            </div>
          )}
        </div>

        {subtitle && (
          <p className="text-xs text-muted-foreground">{subtitle}</p>
        )}

        {progress !== undefined && (
          <div className="space-y-2">
            <div className="h-2 w-full bg-muted rounded-full overflow-hidden">
              <div
                className={cn(
                  'h-full rounded-full transition-all duration-300',
                  colorClasses[progressColor]
                )}
                style={{ width: `${Math.min(progress, 100)}%` }}
              />
            </div>
            <div className="text-xs text-muted-foreground text-right">
              {Math.round(progress)}%
            </div>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

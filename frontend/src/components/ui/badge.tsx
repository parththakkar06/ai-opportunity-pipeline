import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

import { cn } from '@/lib/utils'

// shadcn/ui Badge, restyled: quiet text on the tint surface, 4px radius, no border. Status variants
// always carry words ("Verified 9/10"), never colour alone.
const badgeVariants = cva(
  'inline-flex items-center gap-1 whitespace-nowrap rounded-md px-2 py-0.5 text-xs font-medium num',
  {
    variants: {
      variant: {
        default: 'bg-tint text-ink-2',
        secondary: 'bg-tint text-ink-2',
        outline: 'border border-rule-strong text-ink-2',
        destructive: 'bg-tint text-negative',
        positive: 'bg-tint text-positive',
        caution: 'bg-tint text-caution',
        brand: 'bg-tint text-brand',
      },
    },
    defaultVariants: { variant: 'default' },
  },
)

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />
}

export { Badge, badgeVariants }

import { Slot } from '@radix-ui/react-slot'
import { cva, type VariantProps } from 'class-variance-authority'
import * as React from 'react'

import { cn } from '@/lib/utils'

// shadcn/ui Button, restyled for the paper theme (docs/DESIGN_DIRECTION.md §5.16): primary (brand fill,
// once per view), secondary/outline (hairline), ghost/quiet (text only). 36px, 44px on touch screens.
const buttonVariants = cva(
  'pressable inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0 [@media(pointer:coarse)]:min-h-11',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-sheet text-ink-2 hover:bg-tint hover:text-ink',
        secondary: 'border border-input bg-sheet text-ink-2 hover:bg-tint hover:text-ink',
        ghost: 'text-ink-2 hover:bg-tint hover:text-ink',
        link: 'h-auto px-0 text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-3.5',
        sm: 'h-8 px-2.5 text-[13px]',
        lg: 'h-11 px-5 text-[15px]',
        icon: 'h-9 w-9 [@media(pointer:coarse)]:w-11',
      },
    },
    defaultVariants: { variant: 'default', size: 'default' },
  },
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, type, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...(asChild ? {} : { type: type ?? 'button' })}
        {...props}
      />
    )
  },
)
Button.displayName = 'Button'

export { Button, buttonVariants }

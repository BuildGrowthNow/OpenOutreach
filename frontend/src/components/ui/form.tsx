'use client'

import * as React from 'react'
import * as LabelPrimitive from '@radix-ui/react-label'
import { Slot } from '@radix-ui/react-slot'
import {
  Controller,
  ControllerProps,
  FieldPath,
  FieldValues,
  FormProvider,
  useFormContext,
} from 'react-hook-form'

import { cn } from '@/lib/utils'
import { Label } from '@/components/ui/label'

const Form = FormProvider

type FormFieldContextValue<
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>
> = {
  name: TName
  formItemId: string
  formDescriptionId: string
  formMessageId: string
}

const FormFieldContext = React.createContext<FormFieldContextValue>(
  {} as FormFieldContextValue
)

const FormField = <
  TFieldValues extends FieldValues = FieldValues,
  TName extends FieldPath<TFieldValues> = FieldPath<TFieldValues>
>({
  ...props
}: ControllerProps<TFieldValues, TName>) => {
  const id = React.useId()
  const formItemId = `${id}-form-item`
  const formDescriptionId = `${id}-form-description`
  const formMessageId = `${id}-form-message`

  return (
    <FormFieldContext.Provider value={{ 
      name: props.name,
      formItemId,
      formDescriptionId,
      formMessageId 
    }}>
      <Controller {...props} />
    </FormFieldContext.Provider>
  )
}

const useFormField = () => {
  const fieldContext = React.useContext(FormFieldContext)
  const formContext = useFormContext()

  if (!fieldContext) {
    throw new Error('useFormField should be used within <FormField>')
  }

  return { ...fieldContext, ...formContext }
}

type FormItemContextValue = {
  id: string
}

const FormItemContext = React.createContext<FormItemContextValue>(
  {} as FormItemContextValue
)

const FormItem = React.forwardRef<
  HTMLDivElement,
  React.HTMLAttributes<HTMLDivElement>
>(({ className, ...props }, ref) => {
  const id = React.useId()

  return (
    <FormItemContext.Provider value={{ id }}>
      <div ref={ref} className={cn('space-y-2', className)} {...props} />
    </FormItemContext.Provider>
  )
})
FormItem.displayName = 'FormItem'

const FormLabel = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => {
  const fieldContext = React.useContext(FormFieldContext)
  const formContext = useFormContext()
  
  if (fieldContext && formContext) {
    const error = formContext.getFieldState(fieldContext.name).error
    return (
      <Label
        ref={ref}
        className={cn(!!error && 'text-destructive', className)}
        {...props}
      />
    )
  }
  // If used outside FormField, just render the label
  return <Label ref={ref} className={className} {...props} />
})
FormLabel.displayName = 'FormLabel'

const FormControl = React.forwardRef<
  React.ElementRef<typeof Slot>,
  React.ComponentPropsWithoutRef<typeof Slot>
>(({ ...props }, ref) => {
  const fieldContext = React.useContext(FormFieldContext)
  const formContext = useFormContext()
  
  if (fieldContext && formContext) {
    const error = formContext.getFieldState(fieldContext.name).error
    return <Slot ref={ref} aria-invalid={!!error} {...props} />
  }
  // If used outside FormField, just render the slot
  return <Slot ref={ref} {...props} />
})
FormControl.displayName = 'FormControl'

const FormDescription = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, ...props }, ref) => {
  const fieldContext = React.useContext(FormFieldContext)
  
  if (fieldContext) {
    return (
      <p
        ref={ref}
        id={fieldContext.formDescriptionId}
        className={cn('text-sm text-muted-foreground', className)}
        {...props}
      />
    )
  }
  // If used outside FormField, just render the element
  return <p ref={ref} className={className} {...props} />
})
FormDescription.displayName = 'FormDescription'

const FormMessage = React.forwardRef<
  HTMLParagraphElement,
  React.HTMLAttributes<HTMLParagraphElement>
>(({ className, children, ...props }, ref) => {
  const fieldContext = React.useContext(FormFieldContext)
  const formContext = useFormContext()
  
  if (fieldContext && formContext) {
    const error = formContext.getFieldState(fieldContext.name).error
    const body = error ? String(error?.message) : children

    if (!body) {
      return null
    }

    return (
      <p
        ref={ref}
        id={fieldContext.formMessageId}
        className={cn('text-sm font-medium text-destructive', className)}
        {...props}
      >
        {body}
      </p>
    )
  }
  // If used outside FormField, just render children
  return children ? <p ref={ref} className={className} {...props}>{children}</p> : null
})
FormMessage.displayName = 'FormMessage'

export {
  useFormField,
  Form,
  FormItem,
  FormLabel,
  FormControl,
  FormDescription,
  FormMessage,
  FormField,
}
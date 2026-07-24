'use client'

import { useMemo, useState } from 'react'
import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'
import { z } from 'zod'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Badge } from '@/components/ui/badge'
import { updateSettings, type Settings } from '@/lib/api/dashboard'
import { Icons } from '@/lib/types/components'

const providerValues = [
  'openai',
  'anthropic',
  'google',
  'groq',
  'mistral',
  'cohere',
  'openai_compatible',
] as const

const providerOptions: Array<{
  value: typeof providerValues[number]
  label: string
  description: string
}> = [
  { value: 'openai', label: 'OpenAI', description: 'Best default for hosted GPT models.' },
  { value: 'anthropic', label: 'Anthropic', description: 'Claude-family models focused on long-form reasoning.' },
  { value: 'google', label: 'Google', description: 'Gemini-family models via Google AI / Vertex-backed providers.' },
  { value: 'groq', label: 'Groq', description: 'Very fast hosted inference for supported open models.' },
  { value: 'mistral', label: 'Mistral', description: 'Hosted Mistral models.' },
  { value: 'cohere', label: 'Cohere', description: 'Hosted Cohere models.' },
  { value: 'openai_compatible', label: 'OpenAI-compatible', description: 'Use a custom OpenAI-style endpoint and base URL.' },
]

const llmSchema = z
  .object({
    useCustomLlm: z.boolean(),
    provider: z.enum(providerValues),
    model: z.string().max(200),
    apiKey: z.string().max(500),
    apiBase: z.string().max(500),
    writingStyle: z.string().max(4000),
    sayRules: z.string().max(4000),
    avoidRules: z.string().max(4000),
  })
  .superRefine((values, ctx) => {
    if (values.useCustomLlm) {
      if (!values.model.trim()) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['model'], message: 'Model name is required' })
      }
      if (!values.apiKey.trim()) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiKey'], message: 'API key is required' })
      }
      if (values.provider === 'openai_compatible' && !values.apiBase.trim()) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ['apiBase'], message: 'API base is required for OpenAI-compatible providers' })
      }
    }
  })

type LlmSettingsFormValues = z.infer<typeof llmSchema>

interface LlmSettingsFormProps {
  initialData: Settings['llm']
  onSuccess?: () => void
}

const WRITING_STYLE_SUGGESTION = 'Be concise, conversational, and human. Sound warm and credible. Prefer short LinkedIn-native messages over polished marketing copy.'
const SAY_RULES_SUGGESTION = "Focus on the lead's current workflow, pain points, and what they've tried. Use concrete language from the conversation. Ask one clear next-step question at a time."
const AVOID_RULES_SUGGESTION = 'Do not sound pushy, overhyped, or overly salesy. Do not promise results, claim we already emailed someone, or invent facts about the lead or their company.'

export default function LlmSettingsForm({ initialData, onSuccess }: LlmSettingsFormProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState(false)

  const hasCustomLlm = !!(initialData?.apiKey)

  const form = useForm<LlmSettingsFormValues>({
    resolver: zodResolver(llmSchema),
    defaultValues: {
      useCustomLlm: hasCustomLlm,
      provider: (initialData?.provider as typeof providerValues[number]) || 'openai',
      model: initialData?.model || '',
      apiKey: initialData?.apiKey || '',
      apiBase: initialData?.apiBase || '',
      writingStyle: initialData?.writingStyle || '',
      sayRules: initialData?.sayRules || '',
      avoidRules: initialData?.avoidRules || '',
    },
  })

  const useCustomLlm = form.watch('useCustomLlm')
  const provider = form.watch('provider')
  const model = form.watch('model')
  const apiBase = form.watch('apiBase')
  const writingStyle = form.watch('writingStyle')
  const sayRules = form.watch('sayRules')
  const avoidRules = form.watch('avoidRules')

  const selectedProvider = useMemo(
    () => providerOptions.find((option) => option.value === provider),
    [provider],
  )

  const guidanceCount = [writingStyle, sayRules, avoidRules].filter((value) => value.trim()).length

  const onSubmit = async (values: LlmSettingsFormValues) => {
    try {
      setIsSubmitting(true)
      setError(null)
      setSuccess(false)

      const llmPayload = values.useCustomLlm
        ? {
            provider: values.provider,
            apiKey: values.apiKey.trim(),
            model: values.model.trim(),
            apiBase: values.apiBase.trim(),
            writingStyle: values.writingStyle.trim(),
            sayRules: values.sayRules.trim(),
            avoidRules: values.avoidRules.trim(),
          }
        : {
            // clearing custom LLM — remove key/model/provider so platform default takes over
            provider: '',
            apiKey: '',
            model: '',
            apiBase: '',
            writingStyle: values.writingStyle.trim(),
            sayRules: values.sayRules.trim(),
            avoidRules: values.avoidRules.trim(),
          }

      const response = await updateSettings({ llm: llmPayload })

      if (response.data) {
        setSuccess(true)
        onSuccess?.()
        setTimeout(() => setSuccess(false), 3000)
        return
      }

      setError('Failed to update LLM settings')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An unexpected error occurred')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <Form {...form}>
      <form onSubmit={form.handleSubmit(onSubmit)} className="space-y-6">
        {error && (
          <Alert variant="destructive">
            <Icons.AlertCircle className="h-4 w-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {success && (
          <Alert>
            <Icons.CheckCircle className="h-4 w-4" />
            <AlertDescription>LLM and AI messaging settings updated successfully.</AlertDescription>
          </Alert>
        )}

        {/* Platform LLM banner / BYOK toggle */}
        <div className="rounded-lg border border-zinc-800 bg-zinc-900/60 p-4">
          <div className="flex items-start justify-between gap-4">
            <div className="flex items-start gap-3">
              <Icons.Sparkles className="mt-0.5 h-5 w-5 shrink-0 text-blue-400" />
              <div>
                {useCustomLlm ? (
                  <>
                    <p className="font-medium text-zinc-100">Using your own LLM</p>
                    <p className="mt-0.5 text-sm text-zinc-400">
                      Your API key and model are active. Clear them below to switch back to the Lengrowth AI.
                    </p>
                  </>
                ) : (
                  <>
                    <p className="font-medium text-zinc-100">Running on Lengrowth AI</p>
                    <p className="mt-0.5 text-sm text-zinc-400">
                      No setup needed — we handle the LLM. You can still customise tone and messaging rules below.
                    </p>
                  </>
                )}
              </div>
            </div>
            <Button
              type="button"
              variant={useCustomLlm ? 'outline' : 'secondary'}
              size="sm"
              className="shrink-0"
              onClick={() => form.setValue('useCustomLlm', !useCustomLlm)}
            >
              {useCustomLlm ? 'Use Lengrowth AI' : 'Use my own LLM →'}
            </Button>
          </div>
        </div>

        {/* Custom LLM fields — only shown when user opts in */}
        {useCustomLlm && (
          <div className="space-y-6 rounded-lg border border-zinc-800 bg-zinc-950/40 p-5">
            <div className="grid gap-4 lg:grid-cols-3">
              <Card>
                <CardContent className="pt-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <Icons.Sparkles className="h-4 w-4 text-blue-500" />
                    <h3 className="font-semibold">Provider</h3>
                  </div>
                  <p className="text-lg font-semibold">{selectedProvider?.label || provider}</p>
                  <p className="text-sm text-muted-foreground">{selectedProvider?.description}</p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <Icons.Cpu className="h-4 w-4 text-blue-500" />
                    <h3 className="font-semibold">Model</h3>
                  </div>
                  <p className="truncate text-lg font-semibold">{model || 'Not configured'}</p>
                  <p className="text-sm text-muted-foreground">
                    {provider === 'openai_compatible'
                      ? 'Uses your custom OpenAI-style endpoint.'
                      : 'Uses the provider default endpoint.'}
                  </p>
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-6 space-y-2">
                  <div className="flex items-center gap-2">
                    <Icons.MessageSquare className="h-4 w-4 text-blue-500" />
                    <h3 className="font-semibold">Prompt guardrails</h3>
                  </div>
                  <p className="text-lg font-semibold">{guidanceCount}/3 configured</p>
                  <div className="flex flex-wrap gap-2">
                    {writingStyle.trim() && <Badge variant="outline">Style</Badge>}
                    {sayRules.trim() && <Badge variant="outline">Prefer</Badge>}
                    {avoidRules.trim() && <Badge variant="outline">Avoid</Badge>}
                    {guidanceCount === 0 && <Badge variant="outline">System defaults</Badge>}
                  </div>
                </CardContent>
              </Card>
            </div>

            <div className="grid gap-6 lg:grid-cols-2">
              <FormField
                control={form.control}
                name="provider"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>LLM provider</FormLabel>
                    <Select
                      value={field.value}
                      onValueChange={(value: string | null) => {
                        if (value) field.onChange(value)
                      }}
                    >
                      <FormControl>
                        <SelectTrigger className="w-full">
                          <SelectValue placeholder="Select a provider" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {providerOptions.map((option) => (
                          <SelectItem key={option.value} value={option.value}>
                            {option.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>{selectedProvider?.description}</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={form.control}
                name="model"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Model name</FormLabel>
                    <FormControl>
                      <Input placeholder="e.g. gpt-5-mini, claude-sonnet-5, gemini-2.5-pro" {...field} />
                    </FormControl>
                    <FormDescription>The exact model identifier your provider expects.</FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={form.control}
              name="apiKey"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>API key</FormLabel>
                  <FormControl>
                    <Input
                      type="password"
                      placeholder="sk-… or your provider's key format"
                      autoComplete="off"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>Stored encrypted. Never shared or logged.</FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />

            <FormField
              control={form.control}
              name="apiBase"
              render={({ field }) => (
                <FormItem>
                  <FormLabel>API base URL <span className="text-zinc-500 font-normal">(optional)</span></FormLabel>
                  <FormControl>
                    <Input
                      placeholder="https://api.example.com/v1"
                      {...field}
                    />
                  </FormControl>
                  <FormDescription>
                    {provider === 'openai_compatible'
                      ? 'Required for custom OpenAI-compatible providers.'
                      : 'Only needed for custom or proxy endpoints.'}
                  </FormDescription>
                  <FormMessage />
                </FormItem>
              )}
            />
          </div>
        )}

        {/* Prompt guardrails — always visible */}
        <div className="space-y-2">
          <p className="text-sm font-medium text-zinc-200">Messaging rules</p>
          <p className="text-xs text-zinc-500">These apply regardless of which LLM you use.</p>
        </div>

        <div className="grid gap-6 lg:grid-cols-3">
          <FormField
            control={form.control}
            name="writingStyle"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <FormLabel>Writing style and intent</FormLabel>
                    <FormDescription>High-level tone, pacing, and voice guidance.</FormDescription>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => field.onChange(WRITING_STYLE_SUGGESTION)}
                  >
                    Suggest
                  </Button>
                </div>
                <FormControl>
                  <Textarea
                    rows={8}
                    placeholder="Example: Keep messages brief, curious, and human. Sound like a founder/operator, not a sales sequence."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="sayRules"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <FormLabel>Prefer saying / emphasizing</FormLabel>
                    <FormDescription>Topics, phrases, and approaches the AI should lean into.</FormDescription>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => field.onChange(SAY_RULES_SUGGESTION)}
                  >
                    Suggest
                  </Button>
                </div>
                <FormControl>
                  <Textarea
                    rows={8}
                    placeholder="Example: Ask about current process, team bottlenecks, and what happens when things break."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />

          <FormField
            control={form.control}
            name="avoidRules"
            render={({ field }) => (
              <FormItem>
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <FormLabel>Avoid saying / promising</FormLabel>
                    <FormDescription>Claims, tones, or wording the AI should stay away from.</FormDescription>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => field.onChange(AVOID_RULES_SUGGESTION)}
                  >
                    Suggest
                  </Button>
                </div>
                <FormControl>
                  <Textarea
                    rows={8}
                    placeholder="Example: Do not make unrealistic promises, use heavy hype language, or imply we already contacted someone outside LinkedIn."
                    {...field}
                  />
                </FormControl>
                <FormMessage />
              </FormItem>
            )}
          />
        </div>

        <div className="flex justify-end gap-3 border-t pt-6">
          <Button
            type="button"
            variant="outline"
            onClick={() => form.reset({
              useCustomLlm: hasCustomLlm,
              provider: (initialData?.provider as typeof providerValues[number]) || 'openai',
              model: initialData?.model || '',
              apiKey: initialData?.apiKey || '',
              apiBase: initialData?.apiBase || '',
              writingStyle: initialData?.writingStyle || '',
              sayRules: initialData?.sayRules || '',
              avoidRules: initialData?.avoidRules || '',
            })}
            disabled={isSubmitting}
          >
            Reset
          </Button>
          <Button type="submit" disabled={isSubmitting}>
            {isSubmitting ? (
              <>
                <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : (
              <>
                <Icons.Save className="mr-2 h-4 w-4" />
                Save settings
              </>
            )}
          </Button>
        </div>
      </form>
    </Form>
  )
}

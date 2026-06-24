'use client'

import { useState, useEffect } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Separator } from '@/components/ui/separator'
import { Icons } from '@/lib/types/components'
import { getLinkedInSetupGuide, getLinkedInSetupStatus, getLinkedInCookieInstructions, type LinkedInSetupGuide, type LinkedInSetupStatus, type LinkedInCookieInstructions } from '@/lib/api/dashboard'
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog'

interface LinkedInSetupGuideProps {
  onSetupComplete?: () => void
}

export function LinkedInSetupGuide({ onSetupComplete }: LinkedInSetupGuideProps) {
  const [guide, setGuide] = useState<LinkedInSetupGuide | null>(null)
  const [status, setStatus] = useState<LinkedInSetupStatus | null>(null)
  const [instructions, setInstructions] = useState<LinkedInCookieInstructions | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [showCookieInstructions, setShowCookieInstructions] = useState(false)

  useEffect(() => {
    void (async () => {
      try {
        setLoading(true)
        const [guideRes, statusRes, instructionsRes] = await Promise.all([
          getLinkedInSetupGuide(),
          getLinkedInSetupStatus(),
          getLinkedInCookieInstructions()
        ])
        
        if (guideRes.data) setGuide(guideRes.data)
        if (statusRes.data) setStatus(statusRes.data)
        if (instructionsRes.data) setInstructions(instructionsRes.data)
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load setup guide')
      } finally {
        setLoading(false)
      }
    })()
  }, [])

  const handleStartSetup = async () => {
    // Navigate to settings page - this is simplified, in production you might want to use router.push
    if (typeof window !== 'undefined') {
      window.location.href = '/settings'
    }
  }

  if (loading) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <div className="flex items-center justify-center h-96">
          <div className="flex flex-col items-center gap-4">
            <Icons.RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
            <div className="text-muted-foreground">Loading setup guide...</div>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertTitle>Failed to load</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  if (!guide || !instructions || !status) {
    return (
      <div className="flex-1 p-4 md:p-6 lg:p-8">
        <Alert variant="destructive">
          <Icons.AlertCircle className="h-4 w-4" />
          <AlertTitle>Invalid Data</AlertTitle>
          <AlertDescription>Failed to load setup guide data. Please try again.</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="flex-1 space-y-6 p-4 md:p-6 lg:p-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">LinkedIn Setup Guide</h1>
          <p className="text-muted-foreground mt-1">
            Follow these steps to configure LinkedIn for your outreach campaigns
          </p>
        </div>
        <div className="flex items-center gap-4">
          {status.status.setup_complete ? (
            <Badge variant="outline" className="bg-emerald-50 text-emerald-700 border-emerald-200">
              <Icons.CheckCircle className="mr-2 h-3.5 w-3.5" />
              Setup Complete
            </Badge>
          ) : (
            <Badge variant="outline" className="bg-blue-50 text-blue-700 border-blue-200">
              <Icons.AlertCircle className="mr-2 h-3.5 w-3.5" />
              Setup Required
            </Badge>
          )}
          <Button onClick={handleStartSetup}>
            <Icons.Settings className="mr-2 h-4 w-4" />
            Go to Settings
          </Button>
        </div>
      </div>

      {/* Setup Status Card */}
      <Card>
        <CardHeader>
          <CardTitle>Setup Status</CardTitle>
          <CardDescription>
            Your current LinkedIn configuration status
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className={`p-4 rounded-lg ${status.status.linkedin_profile.exists ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.User className={`h-5 w-5 ${status.status.linkedin_profile.exists ? 'text-green-600' : 'text-red-600'}`} />
                <span className="font-medium">LinkedIn Profile</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {status.status.linkedin_profile.exists ? 'Configured' : 'Not Configured'}
              </div>
              <div className="text-xs mt-1">
                {status.status.linkedin_profile.count} profile(s) found
              </div>
            </div>
            <div className={`p-4 rounded-lg ${status.status.linkedin_credentials.exists ? 'bg-green-50' : 'bg-red-50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.Lock className={`h-5 w-5 ${status.status.linkedin_credentials.exists ? 'text-green-600' : 'text-red-600'}`} />
                <span className="font-medium">LinkedIn Credentials</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {status.status.linkedin_credentials.exists ? 'Configured' : 'Not Configured'}
              </div>
              <div className="text-xs mt-1">
                {status.status.linkedin_credentials.count} credential(s) found
              </div>
            </div>
            <div className={`p-4 rounded-lg ${status.status.setup_complete ? 'bg-green-50' : 'bg-amber-50'}`}>
              <div className="flex items-center gap-2 mb-2">
                <Icons.CheckCircle className={`h-5 w-5 ${status.status.setup_complete ? 'text-green-600' : 'text-amber-600'}`} />
                <span className="font-medium">Overall Status</span>
              </div>
              <div className="text-sm text-muted-foreground">
                {status.status.setup_complete ? 'Ready' : 'In Progress'}
              </div>
              <div className="text-xs mt-1">
                {status.status.setup_progress.current} / {status.status.setup_progress.total} steps complete
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Setup Guide Tabs */}
      <Tabs defaultValue="methods" className="space-y-6">
        <TabsList className="grid grid-cols-3">
          <TabsTrigger value="methods">
            <Icons.Zap className="mr-2 h-4 w-4" />
            Setup Methods
          </TabsTrigger>
          <TabsTrigger value="security">
            <Icons.Lock className="mr-2 h-4 w-4" />
            Security
          </TabsTrigger>
          <TabsTrigger value="troubleshooting">
            <Icons.AlertCircle className="mr-2 h-4 w-4" />
            Troubleshooting
          </TabsTrigger>
        </TabsList>

        {/* Methods Tab */}
        <TabsContent value="methods" className="space-y-6">
          {guide.guide.methods.map((method) => (
            <Card key={method.method}>
              <CardHeader>
                <CardTitle className="flex items-center justify-between">
                  <span>{method.title}</span>
                  <Badge variant="outline">{method.method}</Badge>
                </CardTitle>
                <CardDescription>{method.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="space-y-3">
                    <h4 className="font-medium flex items-center">
                        <Icons.ListTodo className="mr-2 h-4 w-4 text-blue-600" />
                    Steps
                  </h4>
                  <ol className="list-decimal list-inside space-y-2 ml-2">
                    {method.steps.map((step, idx) => (
                      <li key={idx} className="text-sm">{step}</li>
                    ))}
                  </ol>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {method.pros.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium flex items-center">
                        <Icons.Plus className="mr-2 h-4 w-4 text-green-600" />
                       Pros
                      </h4>
                      <ul className="space-y-1">
                        {method.pros.map((pro, idx) => (
                          <li key={idx} className="text-sm text-green-700 dark:text-green-400 flex items-start">
                            <Icons.CheckCircle className="mr-2 h-3.5 w-3.5 flex-shrink-0" />
                            {pro}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  {method.cons.length > 0 && (
                    <div className="space-y-2">
                      <h4 className="font-medium flex items-center">
                        <Icons.XCircle className="mr-2 h-4 w-4 text-red-600" />
                        Cons
                      </h4>
                      <ul className="space-y-1">
                        {method.cons.map((con, idx) => (
                          <li key={idx} className="text-sm text-red-700 dark:text-red-400 flex items-start">
                            <Icons.AlertCircle className="mr-2 h-3.5 w-3.5 flex-shrink-0" />
                            {con}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="pt-4 border-t">
                  <Button 
                    variant={method.method === 'cookie' ? 'outline' : 'default'}
                    className="w-full md:w-auto"
                    onClick={() => {
                      if (method.method === 'cookie') {
                        setShowCookieInstructions(true)
                      }
                    }}
                  >
                    {method.method === 'cookie' ? (
                      <>
                        <Icons.ListTodo className="mr-2 h-4 w-4" />
                        Get Cookie Instructions
                      </>
                    ) : (
                      <>
                        <Icons.Link className="mr-2 h-4 w-4" />
                        Start Setup
                      </>
                    )}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </TabsContent>

        {/* Security Tab */}
        <TabsContent value="security" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Security Best Practices</CardTitle>
              <CardDescription>
                How to keep your LinkedIn credentials secure
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <Alert className="bg-amber-50 border-amber-200">
                <Icons.AlertTriangle className="h-4 w-4 text-amber-600" />
                <AlertTitle className="text-amber-700">Important Security Notice</AlertTitle>
                <AlertDescription className="text-amber-600">
                  Your LinkedIn credentials contain sensitive information. Follow these best practices to keep your account secure.
                </AlertDescription>
              </Alert>
              
              <div className="space-y-4">
                {guide.guide.security.items.map((item, idx) => (
                  <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-muted/30">
                    <Icons.Lock className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                    <p className="text-sm">{item}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Troubleshooting Tab */}
        <TabsContent value="troubleshooting" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Common Issues</CardTitle>
              <CardDescription>
                Solutions to common LinkedIn setup problems
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {guide.guide.troubleshooting.items.map((issue, idx) => (
                <div key={idx} className="border rounded-lg p-4 hover:border-blue-300 transition-colors">
                  <div className="flex items-start gap-3">
                    <Icons.AlertCircle className="h-5 w-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <h4 className="font-medium">{issue.issue}</h4>
                      <p className="text-sm text-muted-foreground mt-1">{issue.solution}</p>
                    </div>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Prerequisites Card */}
      <Card>
        <CardHeader>
          <CardTitle>Prerequisites</CardTitle>
          <CardDescription>
            What you need before starting your LinkedIn setup
          </CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {guide.guide.prerequisites.items.map((item, idx) => (
              <li key={idx} className="flex items-start gap-3">
                <Icons.CheckCircle className="h-5 w-5 text-green-600 flex-shrink-0 mt-0.5" />
                <span className="text-sm">{item}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Next Steps */}
      {guide.guide.next_steps && (
        <Card>
          <CardHeader>
            <CardTitle>Next Steps</CardTitle>
            <CardDescription>
              After completing setup, here's what to do next
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3">
              {guide.guide.next_steps.items.map((item, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <Icons.ArrowRight className="h-5 w-5 text-blue-600 flex-shrink-0 mt-0.5" />
                  <span className="text-sm">{item}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Cookie Instructions Dialog */}
      <Dialog open={showCookieInstructions} onOpenChange={setShowCookieInstructions}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>How to Get LinkedIn Session Cookies</DialogTitle>
            <DialogDescription>
              Follow these steps to extract your LinkedIn session cookies
            </DialogDescription>
          </DialogHeader>
          
          {instructions.instructions && (
            <div className="space-y-6">
              {instructions.instructions.steps.map((step) => (
                <div key={step.step} className="space-y-2">
                  <div className="flex items-center gap-3">
                    <div className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 text-blue-700 font-semibold text-sm">
                      {step.step}
                    </div>
                    <h4 className="font-medium">{step.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground ml-11">{step.description}</p>
                  {step.note && (
                    <div className="ml-11 p-2 bg-amber-50 rounded text-sm text-amber-800">
                      <Icons.AlertCircle className="h-4 w-4 inline mr-2" />
                      {step.note}
                    </div>
                  )}
                </div>
              ))}

              {instructions.instructions.alternative_method && (
                <>
                  <Separator />
                  <div className="space-y-2">
                    <h4 className="font-medium flex items-center">
                      <Icons.Globe className="mr-2 h-4 w-4" />
                      {instructions.instructions.alternative_method.title}
                    </h4>
                    <p className="text-sm text-muted-foreground">
                      {instructions.instructions.alternative_method.description}
                    </p>
                    <ol className="list-decimal list-inside space-y-1 ml-5 text-sm">
                      {instructions.instructions.alternative_method.steps.map((s, idx) => (
                        <li key={idx}>{s}</li>
                      ))}
                    </ol>
                  </div>
                </>
              )}

              {instructions.instructions.security_note && (
                <Alert className="border-amber-200 bg-amber-50">
                  <Icons.Lock className="h-4 w-4 text-amber-600" />
                  <AlertDescription>
                    {instructions.instructions.security_note}
                  </AlertDescription>
                </Alert>
              )}

              {instructions.instructions.verification && (
                <div className="space-y-2">
                  <div className="flex items-center gap-2">
                    <Icons.CheckCircle className="h-5 w-5 text-green-600" />
                    <h4 className="font-medium">{instructions.instructions.verification.title}</h4>
                  </div>
                  <p className="text-sm text-muted-foreground">
                    {instructions.instructions.verification.description}
                  </p>
                  <div className="p-2 bg-green-50 rounded text-sm text-green-700">
                    <Icons.CheckCircle className="h-4 w-4 inline mr-2" />
                    {instructions.instructions.verification.success}
                  </div>
                </div>
              )}
            </div>
          )}
          
          <div className="flex justify-end gap-2 pt-4">
            <Button variant="outline" onClick={() => setShowCookieInstructions(false)}>
              Close
            </Button>
            <Button onClick={() => {
              setShowCookieInstructions(false)
              handleStartSetup()
            }}>
              Go to Settings
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  )
}

export default LinkedInSetupGuide
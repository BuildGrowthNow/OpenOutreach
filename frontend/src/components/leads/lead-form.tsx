"use client";

import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import { Icons } from "@/lib/types/components";
import { Lead, DealState, DealOutcome } from "@/lib/types/components";
import {
  zincDialogContentClassName,
  zincDialogFooterClassName,
  zincDialogHeaderClassName,
  zincInputClassName,
  zincSectionClassName,
  zincSelectContentClassName,
  zincSelectTriggerClassName,
  zincTextareaClassName,
} from "@/lib/modal-styles";

interface LeadFormProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  lead?: Lead;
  onSubmit: (data: Partial<Lead>) => Promise<void>;
  isSubmitting?: boolean;
}

export function LeadForm({
  open,
  onOpenChange,
  lead,
  onSubmit,
  isSubmitting = false,
}: LeadFormProps) {
  const isEditMode = !!lead;
  const title =
    isEditMode && lead?.id ? `Edit Lead - ID: ${lead.id}` : "Add New Lead";

  const [formData, setFormData] = useState<Partial<Lead>>({
    name: lead?.name || "",
    company: lead?.company || "",
    title: lead?.title || "",
    publicIdentifier: lead?.publicIdentifier || "",
    linkedinUrl: lead?.linkedinUrl || "",
    state: lead?.state || ("QUALIFIED" as DealState),
    outcome: lead?.outcome || undefined,
    disqualified: lead?.disqualified || false,
    contactInfo: lead?.contactInfo || { email: "", phoneNumbers: [] },
  });

  const [errors, setErrors] = useState<Record<string, string>>({});

  const validateForm = (): boolean => {
    const newErrors: Record<string, string> = {};

    if (!formData.name?.trim()) {
      newErrors.name = "Name is required";
    }

    if (!formData.publicIdentifier?.trim()) {
      newErrors.publicIdentifier = "Public identifier is required";
    }

    if (
      formData.linkedinUrl &&
      !formData.linkedinUrl.includes("linkedin.com")
    ) {
      newErrors.linkedinUrl = "Please enter a valid LinkedIn URL";
    }

    if (
      formData.contactInfo?.email &&
      !/^\S+@\S+\.\S+$/.test(formData.contactInfo.email)
    ) {
      newErrors.email = "Please enter a valid email address";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!validateForm()) {
      return;
    }

    try {
      await onSubmit(formData);
      handleClose();
    } catch (error) {
      console.error("Failed to submit lead:", error);
    }
  };

  const handleChange = <Field extends keyof Lead>(
    field: Field,
    value: Lead[Field],
  ) => {
    setFormData((prev) => ({
      ...prev,
      [field]: value,
    }));

    // Clear error for this field if it exists
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const handleContactInfoChange = (
    field: keyof NonNullable<Lead["contactInfo"]>,
    value: string | string[],
  ) => {
    setFormData((prev) => ({
      ...prev,
      contactInfo: {
        ...prev.contactInfo,
        [field]: value,
      } as Lead["contactInfo"],
    }));

    // Clear error for this field if it exists
    if (errors[field]) {
      setErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }
  };

  const handleClose = () => {
    setErrors({});
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`${zincDialogContentClassName} max-h-[90vh] overflow-hidden p-0 sm:max-w-[820px]`}
      >
        <DialogHeader
          className={`${zincDialogHeaderClassName} px-6 pt-6 sm:px-8 sm:pt-8`}
        >
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>
            {isEditMode
              ? "Update lead information and status"
              : "Add a new lead to your outreach system"}
          </DialogDescription>
        </DialogHeader>

        <form
          onSubmit={handleSubmit}
          className="space-y-6 overflow-y-auto px-6 py-6 sm:px-8 sm:py-8"
        >
          {/* Basic Information */}
          <div className={`${zincSectionClassName} space-y-4`}>
            <h3 className="text-sm font-medium text-zinc-100">
              Basic Information
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label
                  htmlFor="name"
                  className={errors.name ? "text-red-600" : ""}
                >
                  Full Name *
                </Label>
                <Input
                  id="name"
                  value={formData.name}
                  onChange={(e) => handleChange("name", e.target.value)}
                  placeholder="John Doe"
                  className={cn(
                    zincInputClassName,
                    errors.name && "border-red-600 focus-visible:ring-red-600",
                  )}
                />
                {errors.name && (
                  <p className="text-sm text-red-600">{errors.name}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="company">Company</Label>
                <Input
                  id="company"
                  value={formData.company}
                  onChange={(e) => handleChange("company", e.target.value)}
                  placeholder="Acme Inc."
                  className={zincInputClassName}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="title">Title/Role</Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => handleChange("title", e.target.value)}
                  placeholder="Senior Developer"
                  className={zincInputClassName}
                />
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="publicIdentifier"
                  className={errors.publicIdentifier ? "text-red-600" : ""}
                >
                  Public Identifier *
                </Label>
                <Input
                  id="publicIdentifier"
                  value={formData.publicIdentifier}
                  onChange={(e) =>
                    handleChange("publicIdentifier", e.target.value)
                  }
                  placeholder="john-doe-12345"
                  className={cn(
                    zincInputClassName,
                    errors.publicIdentifier &&
                      "border-red-600 focus-visible:ring-red-600",
                  )}
                />
                {errors.publicIdentifier && (
                  <p className="text-sm text-red-600">
                    {errors.publicIdentifier}
                  </p>
                )}
              </div>

              <div className="space-y-2">
                <Label
                  htmlFor="linkedinUrl"
                  className={errors.linkedinUrl ? "text-red-600" : ""}
                >
                  LinkedIn URL
                </Label>
                <Input
                  id="linkedinUrl"
                  value={formData.linkedinUrl}
                  onChange={(e) => handleChange("linkedinUrl", e.target.value)}
                  placeholder="https://www.linkedin.com/in/johndoe"
                  className={cn(
                    zincInputClassName,
                    errors.linkedinUrl &&
                      "border-red-600 focus-visible:ring-red-600",
                  )}
                />
                {errors.linkedinUrl && (
                  <p className="text-sm text-red-600">{errors.linkedinUrl}</p>
                )}
              </div>
            </div>
          </div>

          {/* Contact Information */}
          <div className={`${zincSectionClassName} space-y-4`}>
            <h3 className="text-sm font-medium text-zinc-100">
              Contact Information
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label
                  htmlFor="email"
                  className={errors.email ? "text-red-600" : ""}
                >
                  Email Address
                </Label>
                <Input
                  id="email"
                  type="email"
                  value={formData.contactInfo?.email || ""}
                  onChange={(e) =>
                    handleContactInfoChange("email", e.target.value)
                  }
                  placeholder="john@example.com"
                  className={cn(
                    zincInputClassName,
                    errors.email && "border-red-600 focus-visible:ring-red-600",
                  )}
                />
                {errors.email && (
                  <p className="text-sm text-red-600">{errors.email}</p>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="state">Status</Label>
                <Select
                  value={formData.state}
                  onValueChange={(value: string | null) => {
                    if (value) handleChange("state", value as DealState);
                  }}
                >
                  <SelectTrigger className={zincSelectTriggerClassName}>
                    <SelectValue placeholder="Select status" />
                  </SelectTrigger>
                  <SelectContent className={zincSelectContentClassName}>
                    <SelectItem value="QUALIFIED">Qualified</SelectItem>
                    <SelectItem value="READY_TO_CONNECT">
                      Ready to Connect
                    </SelectItem>
                    <SelectItem value="PENDING">Pending</SelectItem>
                    <SelectItem value="CONNECTED">Connected</SelectItem>
                    <SelectItem value="COMPLETED">Completed</SelectItem>
                    <SelectItem value="FAILED">Failed</SelectItem>
                    <SelectItem value="NO_EMAIL">No Email</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>

            {/* Additional Contact Fields */}
            <div className="space-y-2">
              <Label htmlFor="notes">Notes</Label>
              <Textarea
                id="notes"
                value={formData.notes || ""}
                onChange={(e) => handleChange("notes", e.target.value)}
                placeholder="Additional notes about this lead..."
                className={`${zincTextareaClassName} min-h-[80px]`}
              />
            </div>
          </div>

          {/* Status & Qualification */}
          <div className={`${zincSectionClassName} space-y-4`}>
            <h3 className="text-sm font-medium text-zinc-100">
              Status & Qualification
            </h3>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="outcome">Outcome (if known)</Label>
                <Select
                  value={formData.outcome || ""}
                  onValueChange={(value: string | null) => {
                    if (value) handleChange("outcome", value as DealOutcome);
                  }}
                >
                  <SelectTrigger className={zincSelectTriggerClassName}>
                    <SelectValue placeholder="Select outcome" />
                  </SelectTrigger>
                  <SelectContent className={zincSelectContentClassName}>
                    <SelectItem value="not_interested">
                      Not Interested
                    </SelectItem>
                    <SelectItem value="interested">Interested</SelectItem>
                    <SelectItem value="scheduled">Scheduled</SelectItem>
                    <SelectItem value="wrong_person">Wrong Person</SelectItem>
                    <SelectItem value="no_response">No Response</SelectItem>
                    <SelectItem value="other">Other</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div className="flex items-center gap-2 rounded-xl border border-zinc-800/80 bg-zinc-900/50 p-4">
                <input
                  type="checkbox"
                  id="disqualified"
                  checked={formData.disqualified}
                  onChange={(e) =>
                    handleChange("disqualified", e.target.checked)
                  }
                  className="h-4 w-4 rounded border-zinc-700 bg-zinc-950 text-zinc-100 shadow-sm focus:ring-2 focus:ring-zinc-600"
                />
                <Label htmlFor="disqualified" className="cursor-pointer">
                  Disqualified
                </Label>
              </div>
            </div>
          </div>

          <DialogFooter className={zincDialogFooterClassName}>
            <Button
              type="button"
              variant="outline"
              className="border-zinc-800 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
              onClick={handleClose}
              disabled={isSubmitting}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Icons.RefreshCw className="mr-2 h-4 w-4 animate-spin" />
                  {isEditMode ? "Updating..." : "Creating..."}
                </>
              ) : (
                <>{isEditMode ? "Update Lead" : "Create Lead"}</>
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

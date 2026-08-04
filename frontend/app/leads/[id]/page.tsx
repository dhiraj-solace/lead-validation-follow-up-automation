import { apiGet, Lead } from "@/lib/api";
import { notFound } from "next/navigation";
import type { ReactNode } from "react";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import { Box, Chip, Stack, Typography } from "@mui/material";
import { EmailStatusChip, PanelCard, ScoreChip, ValidationChip } from "../../ui";
import CallHistory, { CallLog } from "./call-history";
import CallLeadAction from "./call-lead-action";
import ConversationHistory from "./conversation-history";
import EmailDraftPanel from "./email-draft-panel";
import LeadActions from "./lead-actions";

type Message = {
  id: number;
  channel?: string;
  subject: string;
  body: string;
  status: string;
  direction: string;
  sent_at: string;
};

type CallEligibility = {
  eligible: boolean;
  reasons: string[];
  minimum_score: number;
  cooldown_hours: number;
};

function InfoGroup({ children, title }: { children: ReactNode; title: string }) {
  return (
    <Box
      sx={{
        bgcolor: "#f8fafc",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        height: "100%",
        p: 1.35
      }}
    >
      <Typography color="primary.dark" sx={{ fontSize: 11, fontWeight: 950, textTransform: "uppercase" }}>
        {title}
      </Typography>
      <Stack spacing={0.85} sx={{ mt: 1 }}>
        {children}
      </Stack>
    </Box>
  );
}

function InfoRow({ label, value }: { label: string; value?: ReactNode }) {
  return (
    <Box
      sx={{
        alignItems: { xs: "flex-start", sm: "center" },
        display: "grid",
        gap: 0.8,
        gridTemplateColumns: { xs: "1fr", sm: "112px minmax(0, 1fr)" },
        minHeight: 30
      }}
    >
      <Typography color="text.secondary" sx={{ fontSize: 10.5, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      {typeof value === "string" || typeof value === "number" || value == null ? (
        <Typography color="text.primary" sx={{ fontSize: 13.5, fontWeight: 780, overflowWrap: "anywhere" }}>
          {formatValue(value)}
        </Typography>
      ) : (
        value
      )}
    </Box>
  );
}

function NoteBlock({ label, value }: { label: string; value?: string | null }) {
  return (
    <Box sx={{ bgcolor: "#ffffff", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.25 }}>
      <Typography color="text.secondary" sx={{ fontSize: 10.5, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ fontSize: 13.5, fontWeight: 650, mt: 0.45, whiteSpace: "pre-wrap" }}>{formatValue(value)}</Typography>
    </Box>
  );
}

function StatusChip({ label, tone = "neutral" }: { label: string; tone?: "success" | "warning" | "danger" | "neutral" }) {
  const palette = {
    danger: { bgcolor: "#fdecea", color: "#b42318" },
    neutral: { bgcolor: "#eef2f7", color: "#42526a" },
    success: { bgcolor: "#dcfce7", color: "#087443" },
    warning: { bgcolor: "#ffedd5", color: "#9a3412" }
  }[tone];
  return (
    <Chip
      label={label}
      size="small"
      sx={{ ...palette, borderRadius: 999, fontSize: 12, fontWeight: 850, height: 24, maxWidth: "100%" }}
    />
  );
}

function ScoreLabel({ score }: { score: number }) {
  return (
    <Chip
      label={`Score: ${score}`}
      size="small"
      sx={{ bgcolor: "#e6f4f1", color: "#006b5c", fontSize: 12, fontWeight: 900, height: 24 }}
    />
  );
}

function booleanChip(yes: boolean, yesLabel: string, noLabel: string, yesTone: "success" | "danger" = "success") {
  return <StatusChip label={yes ? yesLabel : noLabel} tone={yes ? yesTone : "neutral"} />;
}

function statusTone(value?: string | null): "success" | "warning" | "danger" | "neutral" {
  const normalized = String(value || "").toLowerCase();
  if (["active", "valid", "sent", "consented"].includes(normalized)) {
    return "success";
  }
  if (["invalid", "failed", "rejected"].includes(normalized)) {
    return "danger";
  }
  if (["pending", "not sent", "not_sent"].includes(normalized)) {
    return "warning";
  }
  return "neutral";
}

function statusChip(value?: string | null) {
  const label = toTitleCase(String(value || "Pending").replace(/_/g, " "));
  return <StatusChip label={label} tone={statusTone(label)} />;
}

export default async function LeadDetailPage({ params }: { params: { id: string } }) {
  const lead = await apiGet<Lead & { messages: Message[]; calls: CallLog[]; call_eligibility: CallEligibility }>(
    `/${params.id}`
  ).catch(() => null);
  if (!lead) notFound();

  const displayName = formatDisplayName(lead.name);
  const score = Math.max(0, Math.min(Number(lead.score) || 0, 100));
  const emailAlreadySent = lead.email_sent_status === "sent";

  return (
    <>
      <Stack
        direction={{ xs: "column", md: "row" }}
        spacing={1.5}
        sx={{ alignItems: { xs: "stretch", md: "flex-start" }, justifyContent: "space-between", mb: 2 }}
      >
        <Box>
          <Typography color="primary.dark" sx={{ fontSize: 11, fontWeight: 900, textTransform: "uppercase" }}>
            Lead Detail
          </Typography>
          <Typography component="h1" sx={{ fontSize: { xs: 28, md: 34 }, fontWeight: 950, lineHeight: 1.1, mt: 0.5 }}>
            {displayName}
          </Typography>
          <Typography color="text.secondary" sx={{ fontSize: 15, mt: 0.7 }}>
            Review profile, score, outreach draft, and follow-up status.
          </Typography>
        </Box>
        <Stack
          direction="row"
          spacing={0.75}
          sx={{
            alignItems: "center",
            flexWrap: "wrap",
            gap: 0.75,
            justifyContent: { xs: "flex-start", md: "flex-end" },
            maxWidth: { md: 420 }
          }}
        >
          <ValidationChip status={normalizeStatus(lead.validation_status || "Pending")} />
          <EmailStatusChip status={lead.email_sent_status} />
          <ScoreChip band={lead.score_band} />
          <ScoreLabel score={score} />
        </Stack>
      </Stack>

      <PanelCard
        description={`${formatRequirement(lead)} in ${toTitleCase(lead.location_preference || "Any Location")}`}
        icon={<PersonOutlineOutlinedIcon color="primary" />}
        title="Lead Information"
        sx={{ mb: 2 }}
      >
        <Stack spacing={1.25}>
          <Box
            sx={{
              display: "grid",
              gap: 1.1,
              gridTemplateColumns: { xs: "1fr", md: "repeat(2, minmax(0, 1fr))", lg: "repeat(3, minmax(0, 1fr))" }
            }}
          >
            <InfoGroup title="Contact">
              <InfoRow label="Email" value={lead.email} />
              <InfoRow label="Phone" value={lead.phone} />
              <InfoRow label="Source" value={toTitleCase(lead.source)} />
            </InfoGroup>

            <InfoGroup title="Requirement">
              <InfoRow label="Property Type" value={toTitleCase(lead.property_type)} />
              <InfoRow label="Configuration" value={toTitleCase(lead.configuration)} />
              <InfoRow label="Location" value={toTitleCase(lead.location_preference)} />
              <InfoRow label="Budget" value={lead.budget} />
              <InfoRow label="Timeline" value={toTitleCase(lead.timeline)} />
            </InfoGroup>

            <InfoGroup title="Assignment">
              <InfoRow label="Agent" value={toTitleCase(lead.assigned_agent_name || "Unassigned")} />
              <InfoRow label="Agent Email" value={lead.assigned_agent_email || "No assigned sender"} />
              <InfoRow label="Provider" value={providerLabel(lead.assigned_agent_email_provider)} />
            </InfoGroup>

            <InfoGroup title="Status">
              <InfoRow label="Validation" value={statusChip(lead.validation_status || "Pending")} />
              <InfoRow label="Automation" value={statusChip(lead.automation_status || "Not Started")} />
              <InfoRow label="Call Consent" value={booleanChip(Boolean(lead.call_consent), "Consented", "Not Consented")} />
              <InfoRow label="Do Not Call" value={booleanChip(Boolean(lead.do_not_call), "Yes", "No", "danger")} />
            </InfoGroup>
          </Box>

          <Box sx={{ display: "grid", gap: 1.1, gridTemplateColumns: "1fr" }}>
            <NoteBlock label="Validation Remarks" value={sentenceCase(lead.validation_remarks)} />
            {lead.message ? <NoteBlock label="Lead Message" value={sentenceCase(lead.message)} /> : null}
          </Box>
        </Stack>
      </PanelCard>

      <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", xl: "minmax(0, 1.3fr) 360px" }, mb: 2 }}>
        <EmailDraftPanel
          emailSentStatus={lead.email_sent_status || "not_sent"}
          initialBody={replaceRawLeadName(lead.email_draft_body || "", lead.name, displayName)}
          initialSubject={lead.email_draft_subject || ""}
          leadId={lead.id}
          validationStatus={lead.validation_status || "Pending"}
        />

        <PanelCard
          description={emailAlreadySent ? "Follow-up, WhatsApp, and reply controls." : "Available after the initial email is sent."}
          icon={<CheckCircleOutlineOutlinedIcon color="primary" />}
          title="Next Actions"
        >
          <CallLeadAction
            assignedAgent={toTitleCase(lead.assigned_agent_name || "Unassigned")}
            eligibility={lead.call_eligibility}
            leadId={lead.id}
            leadName={displayName}
            maskedPhone={maskPhone(lead.phone || "")}
          />
          <LeadActions compact leadId={lead.id} emailSentStatus={lead.email_sent_status || "not_sent"} />
          <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, mt: 1.5, p: 1.35 }}>
            <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
              Automation
            </Typography>
            <Typography sx={{ fontWeight: 800, mt: 0.35 }}>{toTitleCase(lead.automation_status || "Not Started")}</Typography>
            {lead.next_followup_at ? (
              <Typography color="text.secondary" variant="body2">
                Next Follow-Up: {formatDateTime(lead.next_followup_at)}
              </Typography>
            ) : null}
          </Box>
        </PanelCard>
      </Box>

      <ConversationHistory
        messages={(lead.messages || []).map((message) => ({
          ...message,
          body: replaceRawLeadName(message.body, lead.name, displayName)
        }))}
      />
      <Box sx={{ mt: 2 }}>
        <CallHistory calls={lead.calls || []} />
      </Box>
    </>
  );
}

function formatDisplayName(value?: string) {
  return toTitleCase(String(value || "Unnamed Lead").replace(/[_-]+/g, " "));
}

function toTitleCase(value?: string | null) {
  const clean = String(value || "").replace(/[_-]+/g, " ").trim();
  if (!clean) {
    return "";
  }
  return clean
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function sentenceCase(value?: string | null) {
  const clean = String(value || "").replace(/[_]+/g, " ").trim();
  if (!clean) {
    return "";
  }
  return clean.charAt(0).toUpperCase() + clean.slice(1);
}

function formatValue(value?: string | number | null) {
  if (value === 0) {
    return "0";
  }
  return value ? String(value) : "-";
}

function formatRequirement(lead: Lead) {
  return [lead.configuration, lead.property_type].filter(Boolean).map((item) => toTitleCase(item)).join(" ") || "Property Requirement";
}

function replaceRawLeadName(value: string, rawName: string | undefined, displayName: string) {
  if (!value || !rawName || rawName === displayName) {
    return value;
  }
  return value.split(rawName).join(displayName);
}

function maskPhone(value: string) {
  const digits = value.replace(/\D/g, "");
  if (digits.length <= 4) {
    return "****";
  }
  return `${"*".repeat(Math.max(digits.length - 4, 4))}${digits.slice(-4)}`;
}

function normalizeStatus(value: string) {
  return toTitleCase(value) || "Pending";
}

function providerLabel(value?: string) {
  const labels: Record<string, string> = {
    gmail: "Gmail / Google Workspace",
    outlook: "Outlook / Microsoft 365",
    yahoo: "Yahoo Mail",
    hostinger: "Hostinger Email",
    custom: "Custom SMTP"
  };
  return labels[String(value || "").toLowerCase()] || "Not Configured";
}

function formatDateTime(value?: string | null) {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString("en-IN", {
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    month: "short",
    year: "numeric"
  });
}

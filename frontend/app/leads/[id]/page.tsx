import { apiGet, Lead } from "@/lib/api";
import { notFound } from "next/navigation";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import PersonOutlineOutlinedIcon from "@mui/icons-material/PersonOutlineOutlined";
import SpeedOutlinedIcon from "@mui/icons-material/SpeedOutlined";
import { Box, Chip, Divider, LinearProgress, Stack, Typography } from "@mui/material";
import { EmailStatusChip, PanelCard, ScoreChip, ValidationChip } from "../../ui";
import ConversationHistory from "./conversation-history";
import EmailDraftPanel from "./email-draft-panel";
import LeadActions from "./lead-actions";

type Message = {
  id: number;
  subject: string;
  body: string;
  status: string;
  direction: string;
  sent_at: string;
};

function DetailRow({ label, value }: { label: string; value?: string | number | null }) {
  return (
    <Box
      sx={{
        bgcolor: "#f8fafc",
        border: "1px solid",
        borderColor: "divider",
        borderRadius: 2,
        minHeight: 54,
        px: 1.35,
        py: 0.9
      }}
    >
      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography color="text.primary" sx={{ fontSize: 14, fontWeight: 760, mt: 0.35, overflowWrap: "anywhere" }}>
        {formatValue(value)}
      </Typography>
    </Box>
  );
}

export default async function LeadDetailPage({ params }: { params: { id: string } }) {
  const lead = await apiGet<Lead & { messages: Message[] }>(`/${params.id}`).catch(() => null);
  if (!lead) notFound();

  const displayName = formatDisplayName(lead.name);
  const score = Math.max(0, Math.min(Number(lead.score) || 0, 100));
  const scoreItems = parseScoreBreakdown(lead.score_breakdown, score);
  const scoreTotal = Math.max(0, Math.min(scoreItems.reduce((total, item) => total + item.points, 0), 100));
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
        <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
          <ValidationChip status={normalizeStatus(lead.validation_status || "Pending")} />
          <EmailStatusChip status={lead.email_sent_status} />
          <ScoreChip band={lead.score_band} />
        </Stack>
      </Stack>

      <Box
        sx={{
          alignItems: "start",
          display: "grid",
          gap: 2,
          gridTemplateColumns: { xs: "1fr", lg: "minmax(0, 1.35fr) 340px" },
          mb: 2
        }}
      >
        <PanelCard
          description={`${formatRequirement(lead)} in ${toTitleCase(lead.location_preference || "Any Location")}`}
          icon={<PersonOutlineOutlinedIcon color="primary" />}
          title="Profile"
        >
          <Stack spacing={1.25}>
            <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
              <DetailRow label="Email" value={lead.email} />
              <DetailRow label="Phone" value={lead.phone} />
              <DetailRow label="Source" value={toTitleCase(lead.source)} />
              <DetailRow label="Interest" value={formatRequirement(lead)} />
              <DetailRow label="Preferred Location" value={toTitleCase(lead.location_preference)} />
              <DetailRow label="Budget" value={lead.budget} />
              <DetailRow label="Timeline" value={toTitleCase(lead.timeline)} />
              <DetailRow label="Assigned Agent" value={toTitleCase(lead.assigned_agent_name || "Unassigned")} />
              <DetailRow label="Agent Sender Email" value={lead.assigned_agent_email || "No assigned sender"} />
              <DetailRow label="Agent Email Provider" value={providerLabel(lead.assigned_agent_email_provider)} />
              <DetailRow label="Automation Status" value={toTitleCase(lead.automation_status)} />
              <DetailRow label="Validation Remarks" value={sentenceCase(lead.validation_remarks)} />
            </Box>

            {lead.message ? (
              <Box sx={{ bgcolor: "#ffffff", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.35 }}>
                <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
                  Lead Message
                </Typography>
                <Typography sx={{ fontSize: 14, mt: 0.5, whiteSpace: "pre-wrap" }}>{sentenceCase(lead.message)}</Typography>
              </Box>
            ) : null}
          </Stack>
        </PanelCard>

        <PanelCard
          description="Score and scoring inputs."
          icon={<SpeedOutlinedIcon color="primary" />}
          title="Score"
          sx={{ alignSelf: "start", width: "100%" }}
        >
          <Stack spacing={1.35}>
            <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2.5, p: 1.6 }}>
              <Stack direction="row" sx={{ alignItems: "flex-end", justifyContent: "space-between" }}>
                <Box>
                  <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
                    Lead Score
                  </Typography>
                  <Typography sx={{ fontSize: 36, fontWeight: 950, lineHeight: 1, mt: 0.5 }}>
                    {score}
                    <Typography component="span" color="text.secondary" sx={{ fontSize: 16, fontWeight: 800 }}>
                      /100
                    </Typography>
                  </Typography>
                </Box>
                <ScoreChip band={lead.score_band} />
              </Stack>
              <LinearProgress
                value={score}
                variant="determinate"
                sx={{
                  bgcolor: "#e7edf4",
                  borderRadius: 99,
                  height: 7,
                  mt: 1.35,
                  "& .MuiLinearProgress-bar": { bgcolor: "#166f5c", borderRadius: 99 }
                }}
              />
            </Box>

            <Box component="details" sx={{ "& summary": { cursor: "pointer", fontWeight: 850, outline: "none" } }}>
              <Typography component="summary" color="text.secondary" sx={{ fontSize: 13 }}>
                Scoring Details ({scoreTotal}/100)
              </Typography>
              <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap", gap: 0.75, mt: 1 }}>
              {scoreItems.map((item) => (
                <Chip
                  key={`${item.label}-${item.points}`}
                  label={`${item.label} ${item.points > 0 ? "+" : ""}${item.points}`}
                  size="small"
                  sx={{
                    bgcolor: item.points < 0 ? "#fdecea" : item.points === 0 ? "#eef2f7" : "#e5f7ef",
                    color: item.points < 0 ? "#bf3b32" : item.points === 0 ? "#42526a" : "#0f7a55",
                    fontWeight: 800,
                    maxWidth: "100%"
                  }}
                />
              ))}
              </Stack>
            </Box>

            <Divider />
            <Stack direction="row" sx={{ alignItems: "center", justifyContent: "space-between" }}>
              <Typography color="text.secondary" sx={{ fontWeight: 850 }}>
                Total
              </Typography>
              <Typography sx={{ fontWeight: 950 }}>{scoreTotal}/100</Typography>
            </Stack>
          </Stack>
        </PanelCard>
      </Box>

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

function parseScoreBreakdown(value: string | undefined, displayedScore: number) {
  const parts = String(value || "")
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
  const parsed = parts.map((part) => {
    const match = part.match(/\(([-+]\d+)\)/);
    const points = match ? Number(match[1]) : 0;
    const label = part.replace(/\s*\([-+]\d+\)\s*/g, "").replace(/\s+-\s+/g, " - ");
    return {
      label: sentenceCase(label),
      points: Number.isFinite(points) ? points : 0
    };
  });

  const total = parsed.reduce((sum, item) => sum + item.points, 0);
  if (parsed.length && total !== displayedScore) {
    parsed.push({
      label: "Score Adjustment",
      points: displayedScore - total
    });
  }

  return parsed.length ? parsed : [{ label: "No Scoring Inputs Available", points: displayedScore }];
}

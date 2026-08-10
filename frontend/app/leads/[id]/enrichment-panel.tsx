"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiPost, Lead } from "@/lib/api";
import AutoFixHighOutlinedIcon from "@mui/icons-material/AutoFixHighOutlined";
import { Alert, Box, Button, Chip, Collapse, LinearProgress, Stack, Typography } from "@mui/material";
import { PanelCard } from "../../ui";

type EnrichResponse = {
  success: boolean;
  message: string;
  lead?: Lead;
  demo?: boolean;
};

export default function EnrichmentPanel({ lead }: { lead: Lead }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [moreInfoOpen, setMoreInfoOpen] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const valid = lead.validation_status === "Valid";
  const profiles = parseProfiles(lead.enrichment_profiles);
  const linkedinProfile = profiles.find(isLinkedInProfile);
  const otherProfiles = profiles.filter((profile) => profile !== linkedinProfile);
  const displayedProfiles = linkedinProfile ? otherProfiles : profiles;
  const enrichmentInfo = parseEnrichmentData(lead.enrichment_data);
  const hasMoreInfo = Boolean(enrichmentInfo);

  async function enrich() {
    setLoading(true);
    setMessage("");
    setError("");
    try {
      const result = await apiPost<EnrichResponse>(`/${lead.id}/enrich`);
      setMessage(result.message || "Lead enrichment complete.");
      router.refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Lead enrichment failed.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PanelCard
      description="Fetch profile data from People Data Labs for valid leads without changing the lead score."
      icon={<AutoFixHighOutlinedIcon color="primary" />}
      title="Lead Enrichment"
    >
      <Stack spacing={1.1}>
        {!valid ? <Alert severity="info">Only valid leads can be enriched.</Alert> : null}
        {message ? <Alert severity="success">{message}</Alert> : null}
        {error ? <Alert severity="error">{error}</Alert> : null}

        <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap" }}>
          <Chip label={`Status: ${label(lead.enrichment_status || "Not Run")}`} size="small" />
          <Chip label={`Confidence: ${lead.enrichment_confidence || 0}/10`} size="small" variant="outlined" />
          <Chip label="Score unchanged" size="small" variant="outlined" />
        </Stack>

        {lead.enrichment_summary ? (
          <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.2 }}>
            <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
              Match Summary
            </Typography>
            <Typography sx={{ fontWeight: 800, mt: 0.35 }}>{lead.enrichment_summary}</Typography>
          </Box>
        ) : null}

        <Box sx={{ display: "grid", gap: 0.8, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
          <Detail label="Name" value={lead.enrichment_full_name} />
          <Detail label="Title" value={lead.enrichment_title} />
          <Detail label="Company" value={lead.enrichment_company} />
          <Detail label="Location" value={lead.enrichment_location} />
        </Box>

        {linkedinProfile ? (
          <Box sx={{ bgcolor: "#eff6ff", border: "1px solid", borderColor: "#bfdbfe", borderRadius: 2, p: 1.2 }}>
            <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
              LinkedIn Profile
            </Typography>
            <Typography component="a" href={linkedinProfile} rel="noreferrer" target="_blank" variant="body2">
              {linkedinProfile}
            </Typography>
          </Box>
        ) : null}

        {displayedProfiles.length ? (
          <Box sx={{ bgcolor: "#f8fafc", borderRadius: 2, p: 1.2 }}>
            <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
              {linkedinProfile ? "Other Profiles" : "Social Profiles"}
            </Typography>
            <Stack spacing={0.5} sx={{ mt: 0.6 }}>
              {displayedProfiles.map((profile) => (
                <Typography component="a" href={profile} key={profile} rel="noreferrer" target="_blank" variant="body2">
                  {profile}
                </Typography>
              ))}
            </Stack>
          </Box>
        ) : null}

        {loading ? <LinearProgress /> : null}
        <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
          <Button disabled={!valid || loading} onClick={enrich} startIcon={<AutoFixHighOutlinedIcon />} variant="contained">
            {loading ? "Enriching..." : lead.enrichment_status ? "Re-Enrich Lead" : "Enrich Lead"}
          </Button>
          <Button disabled={!hasMoreInfo} onClick={() => setMoreInfoOpen((open) => !open)} variant="outlined">
            {moreInfoOpen ? "Hide More Info" : "More Info"}
          </Button>
        </Stack>

        <Collapse in={moreInfoOpen && hasMoreInfo}>
          <Box sx={{ bgcolor: "#0f172a", borderRadius: 2, maxHeight: 420, overflow: "auto", p: 1.4 }}>
            <Typography component="pre" sx={{ color: "#e2e8f0", fontFamily: "monospace", fontSize: 12, m: 0, whiteSpace: "pre-wrap" }}>
              {JSON.stringify(enrichmentInfo, null, 2)}
            </Typography>
          </Box>
        </Collapse>
      </Stack>
    </PanelCard>
  );
}

function Detail({ label: detailLabel, value }: { label: string; value?: string | null }) {
  return (
    <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1 }}>
      <Typography color="text.secondary" sx={{ fontSize: 10.5, fontWeight: 850, textTransform: "uppercase" }}>
        {detailLabel}
      </Typography>
      <Typography sx={{ fontWeight: 800, mt: 0.25, overflowWrap: "anywhere" }}>{value || "-"}</Typography>
    </Box>
  );
}

function label(value: string) {
  return value.replace(/[_-]+/g, " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function parseProfiles(value?: string | string[] | null) {
  if (Array.isArray(value)) {
    return value;
  }
  try {
    const parsed = JSON.parse(String(value || "[]"));
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

function isLinkedInProfile(profile: string) {
  return profile.toLowerCase().includes("linkedin.com/");
}

function parseEnrichmentData(value?: string | Record<string, unknown> | null) {
  if (!value) {
    return null;
  }
  if (typeof value === "object") {
    return Object.keys(value).length ? value : null;
  }
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === "object" && Object.keys(parsed).length ? parsed : null;
  } catch {
    return null;
  }
}

"use client";

import { FormEvent, useState } from "react";
import { apiPost, Lead } from "@/lib/api";
import FileUploadOutlinedIcon from "@mui/icons-material/FileUploadOutlined";
import InsertDriveFileOutlinedIcon from "@mui/icons-material/InsertDriveFileOutlined";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  LinearProgress,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { EmptyState, MetricCard, PageHeader, PanelCard, ScoreChip, ValidationChip } from "../ui";

type UploadResult = {
  total_rows: number;
  created: number;
  merged_duplicates: number;
  auto_drafted: number;
  auto_sent: number;
  hot: number;
  warm: number;
  cold: number;
  valid: number;
  invalid: number;
  duplicate: number;
  leads: Lead[];
};

type ReplaceDuplicateResponse = {
  success: boolean;
  message: string;
  lead: Lead;
  removed_duplicate_id: number;
};

type SkipDuplicateResponse = {
  success: boolean;
  message: string;
  lead_id: number;
};

export default function UploadPage() {
  const [file, setFile] = useState<File | null>(null);
  const [validateContacts, setValidateContacts] = useState(true);
  const [loading, setLoading] = useState(false);
  const [resolvingId, setResolvingId] = useState<number | null>(null);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!file) return;
    setLoading(true);
    setError("");
    setNotice("");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const data = await apiPost<UploadResult>(`/upload-leads?validate_contacts=${validateContacts}`, formData);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed");
    } finally {
      setLoading(false);
    }
  }

  function updateResultLeads(current: UploadResult, leads: Lead[]): UploadResult {
    return {
      ...current,
      leads,
      valid: leads.filter((lead) => lead.validation_status === "Valid").length,
      invalid: leads.filter((lead) => lead.validation_status === "Invalid").length,
      duplicate: leads.filter((lead) => lead.validation_status === "Duplicate").length,
      hot: leads.filter((lead) => lead.score_band === "Hot").length,
      warm: leads.filter((lead) => lead.score_band === "Warm").length,
      cold: leads.filter((lead) => lead.score_band === "Cold").length
    };
  }

  async function replaceDuplicate(lead: Lead) {
    const confirmed = window.confirm(
      `Replace old lead #${lead.duplicate_of} with this uploaded duplicate for ${lead.name}?`
    );
    if (!confirmed) return;

    setResolvingId(lead.id);
    setError("");
    setNotice("");
    try {
      const data = await apiPost<ReplaceDuplicateResponse>(
        `/${lead.id}/duplicates/replace?validate_contacts=${validateContacts}`
      );
      setResult((current) => {
        if (!current) return current;
        const next = current.leads.filter((item) => item.id !== data.removed_duplicate_id);
        const existingIndex = next.findIndex((item) => item.id === data.lead.id);
        if (existingIndex >= 0) {
          next[existingIndex] = data.lead;
        } else {
          next.unshift(data.lead);
        }
        return updateResultLeads(current, next);
      });
      setNotice(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate replacement failed");
    } finally {
      setResolvingId(null);
    }
  }

  async function skipDuplicate(lead: Lead) {
    const confirmed = window.confirm(`Skip this duplicate lead for ${lead.name}?`);
    if (!confirmed) return;

    setResolvingId(lead.id);
    setError("");
    setNotice("");
    try {
      const data = await apiPost<SkipDuplicateResponse>(`/${lead.id}/duplicates/skip`);
      setResult((current) => {
        if (!current) return current;
        const next = current.leads.filter((item) => item.id !== data.lead_id);
        return updateResultLeads(current, next);
      });
      setNotice(data.message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Duplicate skip failed");
    } finally {
      setResolvingId(null);
    }
  }

  return (
    <>
      <PageHeader
        description="Upload CSV or Excel leads, run validation, and resolve duplicates before sales outreach."
        eyebrow="Upload"
        title="Import fixed-format lead file"
      />

      <Box sx={{ display: "grid", gap: 1.75, gridTemplateColumns: "1fr" }}>
        <PanelCard
          icon={<FileUploadOutlinedIcon color="primary" />}
          description="CSV and XLSX files are supported."
          title="Upload leads"
        >
          <Box component="form" onSubmit={submit}>
            <Stack spacing={2}>
              <Stack
                direction={{ xs: "column", sm: "row" }}
                spacing={1.5}
                sx={{ alignItems: { xs: "stretch", sm: "center" } }}
              >
                <Button component="label" startIcon={<InsertDriveFileOutlinedIcon />} variant="outlined">
                  Choose file
                  <input
                    accept=".csv,.xlsx"
                    hidden
                    type="file"
                    onChange={(event) => setFile(event.target.files?.[0] || null)}
                  />
                </Button>
                <Typography color={file ? "text.primary" : "text.secondary"}>
                  {file ? file.name : "No file selected"}
                </Typography>
              </Stack>

              <FormControlLabel
                control={
                  <Checkbox
                    checked={validateContacts}
                    onChange={(event) => setValidateContacts(event.target.checked)}
                  />
                }
                label="Run email and phone validation"
                sx={{
                  bgcolor: "#f9fbfd",
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 2,
                  m: 0,
                  px: 1.25,
                  py: 0.5
                }}
              />

              <Button disabled={!file || loading} startIcon={<FileUploadOutlinedIcon />} type="submit" variant="contained">
                {loading ? "Processing..." : "Upload Leads"}
              </Button>
              {loading ? <LinearProgress /> : null}
            </Stack>
          </Box>

          {error ? (
            <Alert severity="error" sx={{ mt: 2 }}>
              {error}
            </Alert>
          ) : null}
          {notice ? (
            <Alert severity="success" sx={{ mt: 2 }}>
              {notice}
            </Alert>
          ) : null}

          {result ? (
            <Box
              sx={{
                display: "grid",
                gap: 1.5,
                gridTemplateColumns: { xs: "1fr", sm: "repeat(2, minmax(0, 1fr))", lg: "repeat(5, minmax(0, 1fr))" },
                mt: 1.75
              }}
            >
              {[
                { label: "Rows", value: result.total_rows },
                { label: "Created", value: result.created },
                { label: "Duplicates", value: result.merged_duplicates },
                { label: "Draft Ready", value: result.auto_drafted },
                { label: "Auto Sent", value: result.auto_sent }
              ].map((item) => (
                <MetricCard key={item.label} label={item.label} value={item.value} />
              ))}
            </Box>
          ) : null}

          {result?.leads?.length ? (
            <TableContainer
              sx={{
                border: "1px solid",
                borderColor: "divider",
                borderRadius: 2,
                maxWidth: "100%",
                mt: 1.75,
                overflowX: "auto",
                WebkitOverflowScrolling: "touch"
              }}
            >
              <Table size="small" sx={{ minWidth: 1040, tableLayout: "fixed" }}>
                <TableHead>
                  <TableRow>
                    <TableCell sx={{ width: 190 }}>Name</TableCell>
                    <TableCell sx={{ width: 240 }}>Contact</TableCell>
                    <TableCell sx={{ width: 130 }}>Validation</TableCell>
                    <TableCell sx={{ width: 120 }}>Score</TableCell>
                    <TableCell sx={{ width: 160 }}>Email Draft</TableCell>
                    <TableCell sx={{ width: 280 }}>Remarks</TableCell>
                    <TableCell sx={{ width: 180 }}>Action</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {result.leads.map((lead) => (
                    <TableRow hover key={lead.id}>
                      <TableCell>
                        <Typography sx={{ fontWeight: 800 }}>{lead.name}</Typography>
                      </TableCell>
                      <TableCell>
                        <Typography>{lead.email || "-"}</Typography>
                        <Typography color="text.secondary" variant="body2">
                          {lead.phone || "-"}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <ValidationChip status={lead.validation_status || "Pending"} />
                      </TableCell>
                      <TableCell>
                        <Stack spacing={0.75} sx={{ alignItems: "flex-start" }}>
                          <Typography>{lead.score}</Typography>
                          <ScoreChip band={lead.score_band} />
                        </Stack>
                      </TableCell>
                      <TableCell>
                        <Typography color={lead.email_draft_subject ? "success.main" : "text.secondary"} sx={{ fontWeight: 800 }}>
                          {lead.email_draft_subject ? "Draft Ready" : "Not Created"}
                        </Typography>
                        {lead.validation_status === "Valid" && lead.score_band === "Hot" && !lead.email_draft_subject ? (
                          <Typography color="text.secondary" variant="body2">
                            Open lead to generate manually
                          </Typography>
                        ) : null}
                      </TableCell>
                      <TableCell>{lead.validation_remarks || "-"}</TableCell>
                      <TableCell>
                        {lead.validation_status === "Duplicate" ? (
                          <Stack direction={{ xs: "column", sm: "row" }} spacing={1}>
                            <Button
                              disabled={resolvingId === lead.id}
                              onClick={() => replaceDuplicate(lead)}
                              size="small"
                              variant="outlined"
                            >
                              Replace Old
                            </Button>
                            <Button
                              color="inherit"
                              disabled={resolvingId === lead.id}
                              onClick={() => skipDuplicate(lead)}
                              size="small"
                              variant="outlined"
                            >
                              Skip
                            </Button>
                          </Stack>
                        ) : (
                          <Typography color="text.secondary">-</Typography>
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          ) : result ? (
            <Box sx={{ mt: 2.25 }}>
              <EmptyState title="No rows imported" description="Check the file format and try uploading again." />
            </Box>
          ) : null}
        </PanelCard>

      </Box>
    </>
  );
}

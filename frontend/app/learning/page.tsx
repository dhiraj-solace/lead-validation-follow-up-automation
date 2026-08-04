"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import CheckCircleOutlineOutlinedIcon from "@mui/icons-material/CheckCircleOutlineOutlined";
import DeleteOutlineOutlinedIcon from "@mui/icons-material/DeleteOutlineOutlined";
import ErrorOutlineOutlinedIcon from "@mui/icons-material/ErrorOutlineOutlined";
import HistoryOutlinedIcon from "@mui/icons-material/HistoryOutlined";
import RestoreOutlinedIcon from "@mui/icons-material/RestoreOutlined";
import VisibilityOutlinedIcon from "@mui/icons-material/VisibilityOutlined";
import {
  Alert,
  Box,
  Button,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  LinearProgress,
  Stack,
  Tab,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableRow,
  Tabs,
  TextField,
  Typography
} from "@mui/material";
import { apiDelete, apiGet, apiPatch } from "@/lib/api";
import { MetricCard, PageHeader, PanelCard } from "../ui";

type LearningStats = {
  total: number;
  gold: number;
  error: number;
  inactive: number;
  avg_judge_score: number;
  avg_attempts: number;
  total_tokens: number;
  estimated_cost: number;
  avg_latency_ms: number;
};

type LearningRecord = {
  id: number;
  lead_id: number;
  lead_name?: string;
  lead_email?: string;
  lead_score_band?: string;
  campaign_type?: string;
  provider?: string;
  llm_provider?: string;
  model?: string;
  tone?: string;
  subject?: string;
  body?: string;
  final_subject?: string;
  final_body?: string;
  selected_version?: string;
  user_action?: string;
  user_feedback?: string;
  guardrail_passed?: number;
  guardrail_issues?: string;
  judge_score?: number;
  judge_status?: string;
  judge_reason?: string;
  is_active?: number;
  review_status?: string;
  admin_note?: string;
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
  estimated_cost?: number;
  latency_ms?: number;
  error_message?: string;
  created_at?: string;
  updated_at?: string;
};

const tabMap = [
  { label: "Gold Examples", status: "gold", active: "true" },
  { label: "Error Examples", status: "error", active: "true" },
  { label: "All Logs", status: "all", active: "all" },
  { label: "Inactive", status: "all", active: "false" }
];

export default function LearningPage() {
  const [tab, setTab] = useState(0);
  const [records, setRecords] = useState<LearningRecord[]>([]);
  const [stats, setStats] = useState<LearningStats | null>(null);
  const [selected, setSelected] = useState<LearningRecord | null>(null);
  const [adminNote, setAdminNote] = useState("");
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState("");
  const [error, setError] = useState("");

  const currentFilter = tabMap[tab];

  useEffect(() => {
    loadData();
  }, [tab]);

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      const activeQuery = currentFilter.active === "all" ? "" : `&active=${currentFilter.active}`;
      const [nextStats, nextRecords] = await Promise.all([
        apiGet<LearningStats>("/learning/stats"),
        apiGet<LearningRecord[]>(`/learning/history?status=${currentFilter.status}${activeQuery}`)
      ]);
      setStats(nextStats);
      setRecords(nextRecords);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load learning data");
    } finally {
      setLoading(false);
    }
  }

  async function reviewRecord(record: LearningRecord, action: "approved" | "rejected") {
    setActionLoading(`${action}-${record.id}`);
    setError("");
    try {
      await apiPatch<LearningRecord>(`/learning/history/${record.id}`, { action, admin_note: adminNote });
      setAdminNote("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update learning record");
    } finally {
      setActionLoading("");
    }
  }

  async function setRecordActive(record: LearningRecord, isActive: boolean) {
    setActionLoading(`${isActive ? "restore" : "remove"}-${record.id}`);
    setError("");
    try {
      if (isActive) {
        await apiPatch<LearningRecord>(`/learning/history/${record.id}/active`, {
          is_active: true,
          admin_note: adminNote || "Restored to learning by admin."
        });
      } else {
        await apiDelete<LearningRecord>(`/learning/history/${record.id}`);
      }
      setAdminNote("");
      await loadData();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update learning status");
    } finally {
      setActionLoading("");
    }
  }

  const statCards = useMemo(
    () => [
      { label: "Total Draft Logs", value: stats?.total ?? 0, hint: "All generated, edited, sent, and reviewed drafts" },
      { label: "Gold Examples", value: stats?.gold ?? 0, hint: "Active approved examples used by RAG" },
      { label: "Error Examples", value: stats?.error ?? 0, hint: "Active failed or rejected examples to avoid" },
      { label: "Avg Judge Score", value: stats?.avg_judge_score ?? 0, hint: `Avg attempts: ${stats?.avg_attempts ?? 0}` },
      { label: "LLM Usage", value: stats?.total_tokens ?? 0, hint: `Cost: $${Number(stats?.estimated_cost ?? 0).toFixed(4)}` }
    ],
    [stats]
  );

  return (
    <>
      <PageHeader
        eyebrow="Admin"
        title="AI Learning"
        description="Manage gold examples, error examples, and AI generation logs used by future email writing."
      />

      <Box
        sx={{
          display: "grid",
          gap: 1.5,
          gridTemplateColumns: { xs: "1fr", sm: "repeat(2, 1fr)", lg: "repeat(5, 1fr)" },
          mb: 2
        }}
      >
        {statCards.map((card) => (
          <MetricCard key={card.label} {...card} />
        ))}
      </Box>

      <PanelCard
        action={
          <Button disabled={loading} onClick={loadData} startIcon={<HistoryOutlinedIcon />} variant="outlined">
            Refresh
          </Button>
        }
        title="Learning Records"
        description="Approve old emails as gold examples, mark weak drafts as error examples, or remove records from active RAG usage."
      >
        <Stack spacing={2}>
          {error ? <Alert severity="error">{error}</Alert> : null}
          <Tabs
            onChange={(_, value) => setTab(value)}
            value={tab}
            variant="scrollable"
            scrollButtons="auto"
            sx={{ borderBottom: "1px solid", borderColor: "divider", minHeight: 42 }}
          >
            {tabMap.map((item) => (
              <Tab key={item.label} label={item.label} sx={{ minHeight: 42, textTransform: "none", fontWeight: 850 }} />
            ))}
          </Tabs>
          {loading ? <LinearProgress /> : null}
          <Box sx={{ overflowX: "auto" }}>
            <Table size="small" sx={{ minWidth: 1180 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Date</TableCell>
                  <TableCell>Lead</TableCell>
                  <TableCell>Campaign</TableCell>
                  <TableCell>Subject</TableCell>
                  <TableCell>Status</TableCell>
                  <TableCell>Judge</TableCell>
                  <TableCell>Usage</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {records.map((record) => (
                  <TableRow key={record.id} hover>
                    <TableCell>{formatDate(record.updated_at || record.created_at)}</TableCell>
                    <TableCell>
                      <Stack spacing={0.25}>
                        <Button
                          LinkComponent={Link}
                          href={`/leads/${record.lead_id}`}
                          sx={{ alignSelf: "flex-start", p: 0, textTransform: "none", fontWeight: 850 }}
                          variant="text"
                        >
                          {formatName(record.lead_name || `Lead ${record.lead_id}`)}
                        </Button>
                        <Typography color="text.secondary" variant="body2">
                          {record.lead_email || "-"}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.75} sx={{ flexWrap: "wrap" }}>
                        <Chip label={formatName(record.campaign_type || record.lead_score_band || "General")} size="small" />
                        <Chip label={formatName(record.provider || "Unknown")} size="small" variant="outlined" />
                      </Stack>
                    </TableCell>
                    <TableCell sx={{ maxWidth: 310 }}>
                      <Typography noWrap sx={{ fontWeight: 800 }}>
                        {record.final_subject || record.subject || "-"}
                      </Typography>
                      <Typography color="text.secondary" noWrap variant="body2">
                        {preview(record.final_body || record.body)}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <StatusChip record={record} />
                    </TableCell>
                    <TableCell>
                      <Stack spacing={0.3}>
                        <Typography sx={{ fontWeight: 850 }}>{record.judge_score ?? 0}/100</Typography>
                        <Typography color="text.secondary" variant="body2">
                          {formatName(record.judge_status || "Pending")}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Typography sx={{ fontWeight: 850 }}>{record.total_tokens || 0} tokens</Typography>
                      <Typography color="text.secondary" variant="body2">
                        {record.latency_ms ? `${record.latency_ms} ms` : "No timing"} / ${Number(record.estimated_cost || 0).toFixed(4)}
                      </Typography>
                    </TableCell>
                    <TableCell align="right">
                      <Stack direction="row" spacing={0.75} sx={{ justifyContent: "flex-end" }}>
                        <Button onClick={() => setSelected(record)} startIcon={<VisibilityOutlinedIcon />} size="small" variant="outlined">
                          View
                        </Button>
                        <Button
                          color="success"
                          disabled={Boolean(actionLoading)}
                          onClick={() => reviewRecord(record, "approved")}
                          startIcon={<CheckCircleOutlineOutlinedIcon />}
                          size="small"
                          variant="outlined"
                        >
                          Gold
                        </Button>
                        <Button
                          color="error"
                          disabled={Boolean(actionLoading)}
                          onClick={() => reviewRecord(record, "rejected")}
                          startIcon={<ErrorOutlineOutlinedIcon />}
                          size="small"
                          variant="outlined"
                        >
                          Error
                        </Button>
                        {record.is_active === 0 ? (
                          <Button
                            disabled={Boolean(actionLoading)}
                            onClick={() => setRecordActive(record, true)}
                            startIcon={<RestoreOutlinedIcon />}
                            size="small"
                            variant="outlined"
                          >
                            Restore
                          </Button>
                        ) : (
                          <Button
                            color="inherit"
                            disabled={Boolean(actionLoading)}
                            onClick={() => setRecordActive(record, false)}
                            startIcon={<DeleteOutlineOutlinedIcon />}
                            size="small"
                            variant="outlined"
                          >
                            Remove
                          </Button>
                        )}
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
                {!loading && !records.length ? (
                  <TableRow>
                    <TableCell colSpan={8}>
                      <Box sx={{ bgcolor: "#f8fafc", border: "1px dashed", borderColor: "divider", borderRadius: 2, p: 4, textAlign: "center" }}>
                        <Typography sx={{ fontWeight: 900 }}>No learning records found</Typography>
                        <Typography color="text.secondary" sx={{ mt: 0.5 }}>
                          Generate or review emails to populate this admin view.
                        </Typography>
                      </Box>
                    </TableCell>
                  </TableRow>
                ) : null}
              </TableBody>
            </Table>
          </Box>
        </Stack>
      </PanelCard>

      <Dialog fullWidth maxWidth="md" onClose={() => setSelected(null)} open={Boolean(selected)}>
        <DialogTitle>Learning Record Detail</DialogTitle>
        <DialogContent dividers>
          {selected ? (
            <Stack spacing={2}>
              <Stack direction="row" spacing={1} sx={{ flexWrap: "wrap" }}>
                <StatusChip record={selected} />
                <Chip label={`Judge ${selected.judge_score ?? 0}/100`} />
                <Chip label={selected.is_active === 0 ? "Inactive" : "Active"} color={selected.is_active === 0 ? "default" : "success"} />
                <Chip label={formatName(selected.llm_provider || selected.provider || "Unknown Provider")} variant="outlined" />
              </Stack>
              <DetailBlock label="Subject" value={selected.final_subject || selected.subject || "-"} />
              <DetailBlock label="Body" value={selected.final_body || selected.body || "-"} multiline />
              <Box sx={{ display: "grid", gap: 1, gridTemplateColumns: { xs: "1fr", md: "1fr 1fr" } }}>
                <DetailBlock label="Human Feedback" value={selected.user_feedback || "-"} multiline />
                <DetailBlock label="Admin Note" value={selected.admin_note || "-"} multiline />
                <DetailBlock label="Judge Reason" value={selected.judge_reason || "-"} multiline />
                <DetailBlock label="Guardrail Issues" value={parseIssues(selected.guardrail_issues).join("\n") || "No guardrail issues"} multiline />
                <DetailBlock label="Model" value={selected.model || "Not captured"} />
                <DetailBlock label="Usage" value={`${selected.total_tokens || 0} tokens / $${Number(selected.estimated_cost || 0).toFixed(4)} / ${selected.latency_ms || 0} ms`} />
                <DetailBlock label="Error Message" value={selected.error_message || "-"} multiline />
                <DetailBlock label="Created" value={formatDate(selected.created_at)} />
              </Box>
              <TextField
                label="Admin note for next action"
                multiline
                minRows={2}
                onChange={(event) => setAdminNote(event.target.value)}
                placeholder="Example: Good CTA style, but only use for hot apartment leads."
                size="small"
                value={adminNote}
              />
            </Stack>
          ) : null}
        </DialogContent>
        <DialogActions sx={{ flexWrap: "wrap", gap: 1, p: 2 }}>
          <Button onClick={() => setSelected(null)}>Close</Button>
          {selected ? (
            <>
              <Button color="success" onClick={() => reviewRecord(selected, "approved")} startIcon={<CheckCircleOutlineOutlinedIcon />} variant="outlined">
                Approve as Gold
              </Button>
              <Button color="error" onClick={() => reviewRecord(selected, "rejected")} startIcon={<ErrorOutlineOutlinedIcon />} variant="outlined">
                Mark as Error
              </Button>
              <Button onClick={() => setRecordActive(selected, selected.is_active === 0)} variant="contained">
                {selected.is_active === 0 ? "Restore to Learning" : "Remove from Learning"}
              </Button>
            </>
          ) : null}
        </DialogActions>
      </Dialog>
    </>
  );
}

function StatusChip({ record }: { record: LearningRecord }) {
  const action = String(record.user_action || "generated").toLowerCase();
  if (record.is_active === 0) {
    return <Chip label="Inactive" size="small" />;
  }
  if (action === "approved" || action === "sent") {
    return <Chip color="success" label="Gold Example" size="small" />;
  }
  if (action === "rejected" || record.guardrail_passed === 0 || ["needs_review", "blocked"].includes(String(record.judge_status))) {
    return <Chip color="error" label="Error Example" size="small" />;
  }
  return <Chip label={formatName(action)} size="small" />;
}

function DetailBlock({ label, value, multiline = false }: { label: string; value: string; multiline?: boolean }) {
  return (
    <Box sx={{ bgcolor: "#f8fafc", border: "1px solid", borderColor: "divider", borderRadius: 2, p: 1.35 }}>
      <Typography color="text.secondary" sx={{ fontSize: 11, fontWeight: 850, textTransform: "uppercase" }}>
        {label}
      </Typography>
      <Typography sx={{ mt: 0.5, overflowWrap: "anywhere", whiteSpace: multiline ? "pre-wrap" : "normal" }}>{value}</Typography>
    </Box>
  );
}

function formatName(value?: string) {
  const clean = String(value || "").replace(/[_-]+/g, " ").trim();
  if (!clean) {
    return "-";
  }
  return clean
    .toLowerCase()
    .split(/\s+/)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function preview(value?: string) {
  const clean = String(value || "").replace(/\s+/g, " ").trim();
  return clean.length > 110 ? `${clean.slice(0, 110)}...` : clean || "-";
}

function formatDate(value?: string) {
  if (!value) {
    return "-";
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

function parseIssues(value?: string) {
  try {
    const parsed = JSON.parse(String(value || "[]"));
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return value ? [value] : [];
  }
}

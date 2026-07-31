"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import AddCircleOutlineOutlinedIcon from "@mui/icons-material/AddCircleOutlineOutlined";
import ArticleOutlinedIcon from "@mui/icons-material/ArticleOutlined";
import {
  Alert,
  Box,
  Button,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  MenuItem,
  Skeleton,
  Stack,
  TextField,
  Typography
} from "@mui/material";
import { EmptyState, PageHeader, PanelCard, ScoreChip } from "../ui";

type Template = {
  id: number;
  name: string;
  category: string;
  property_type: string;
  subject: string;
  body: string;
};

const emptyForm = {
  name: "",
  category: "Hot",
  property_type: "",
  subject: "",
  body: ""
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    try {
      setTemplates(await apiGet<Template[]>("/templates/list"));
      setError("");
    } catch {
      setTemplates([]);
      setError("Could not load templates. Check that the backend is running.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  function closeModal() {
    if (submitting) return;
    setModalOpen(false);
    setForm(emptyForm);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    setNotice("");
    try {
      await apiPost("/templates", { ...form, active: true, reply_rate: 0, conversion_rate: 0 });
      setForm(emptyForm);
      setModalOpen(false);
      setNotice("Template added successfully.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Template creation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        action={
          <Button onClick={() => setModalOpen(true)} startIcon={<AddCircleOutlineOutlinedIcon />} variant="contained">
            Add Template
          </Button>
        }
        description="Maintain reusable message examples used by the AI email writer and follow-up flow."
        eyebrow="Templates"
        title="Email message library"
      />

      <PanelCard
        action={
          <Button onClick={() => setModalOpen(true)} startIcon={<AddCircleOutlineOutlinedIcon />} variant="outlined">
            Add Template
          </Button>
        }
        description={`${templates.length} reusable messages available for AI draft generation.`}
        icon={<ArticleOutlinedIcon color="primary" />}
        title="Active templates"
      >
        {notice ? (
          <Alert severity="success" sx={{ mb: 2 }}>
            {notice}
          </Alert>
        ) : null}
        {error && !modalOpen ? (
          <Alert severity="error" sx={{ mb: 2 }}>
            {error}
          </Alert>
        ) : null}

        {loading ? (
          <Skeleton height={220} variant="rounded" />
        ) : templates.length ? (
          <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", lg: "1fr 1fr" } }}>
            {templates.map((template) => (
              <Box
                key={template.id}
                sx={{
                  bgcolor: "#f8fafc",
                  border: "1px solid",
                  borderColor: "divider",
                  borderRadius: 2,
                  p: 2
                }}
              >
                <Stack direction="row" spacing={1.5} sx={{ alignItems: "flex-start", justifyContent: "space-between" }}>
                  <Box sx={{ minWidth: 0 }}>
                    <Typography sx={{ fontWeight: 900, overflowWrap: "anywhere" }}>{template.name}</Typography>
                    <Typography color="text.secondary" sx={{ mt: 0.5 }} variant="body2">
                      {template.property_type || "Any property"}
                    </Typography>
                  </Box>
                  <ScoreChip band={template.category} />
                </Stack>
                <Typography sx={{ fontWeight: 800, mt: 1.25, overflowWrap: "anywhere" }}>{template.subject}</Typography>
                <Typography color="text.secondary" sx={{ mt: 0.75 }} variant="body2">
                  {compactBody(template.body)}
                </Typography>
              </Box>
            ))}
          </Box>
        ) : (
          <EmptyState title="No templates found" description="Add a starting email template for hot, warm, or cold leads." />
        )}
      </PanelCard>

      <Dialog fullWidth maxWidth="md" onClose={closeModal} open={modalOpen}>
        <Box component="form" onSubmit={submit}>
          <DialogTitle sx={{ pb: 1 }}>
            <Stack spacing={0.5}>
              <Typography component="span" sx={{ fontSize: 24, fontWeight: 900 }}>
                Add Template
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Create a reusable email pattern for AI generation and follow-up messages.
              </Typography>
            </Stack>
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={2} sx={{ pt: 0.5 }}>
              <Box sx={{ display: "grid", gap: 2, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                <TextField label="Name" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                <TextField
                  label="Category"
                  select
                  value={form.category}
                  onChange={(event) => setForm({ ...form, category: event.target.value })}
                >
                  <MenuItem value="Hot">Hot</MenuItem>
                  <MenuItem value="Warm">Warm</MenuItem>
                  <MenuItem value="Cold">Cold</MenuItem>
                </TextField>
              </Box>
              <TextField label="Property type" value={form.property_type} onChange={(event) => setForm({ ...form, property_type: event.target.value })} />
              <TextField label="Subject" required value={form.subject} onChange={(event) => setForm({ ...form, subject: event.target.value })} />
              <TextField
                label="Body"
                minRows={8}
                multiline
                required
                value={form.body}
                onChange={(event) => setForm({ ...form, body: event.target.value })}
              />
              {error && modalOpen ? <Alert severity="error">{error}</Alert> : null}
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button disabled={submitting} onClick={closeModal} variant="outlined">
              Cancel
            </Button>
            <Button
              disabled={submitting || !form.name || !form.subject || !form.body}
              startIcon={<AddCircleOutlineOutlinedIcon />}
              type="submit"
              variant="contained"
            >
              {submitting ? "Saving..." : "Save Template"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </>
  );
}

function compactBody(value: string) {
  return value.length > 190 ? `${value.slice(0, 190)}...` : value;
}

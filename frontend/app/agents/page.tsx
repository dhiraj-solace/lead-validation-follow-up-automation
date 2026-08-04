"use client";

import { FormEvent, useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";
import AddOutlinedIcon from "@mui/icons-material/AddOutlined";
import GroupAddOutlinedIcon from "@mui/icons-material/GroupAddOutlined";
import GroupsOutlinedIcon from "@mui/icons-material/GroupsOutlined";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  Chip,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControlLabel,
  MenuItem,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Typography
} from "@mui/material";
import { EmptyState, PageHeader, PanelCard } from "../ui";

type Agent = {
  id: number;
  name: string;
  email: string;
  territory: string;
  property_type: string;
  email_provider?: string;
  email_username?: string;
  smtp_host?: string;
  smtp_port?: number;
  smtp_use_tls?: number;
  email_account_active?: number;
  active: number;
};

const EMAIL_PROVIDERS = [
  { value: "gmail", label: "Gmail / Google Workspace" },
  { value: "outlook", label: "Outlook / Microsoft 365" },
  { value: "yahoo", label: "Yahoo Mail" },
  { value: "hostinger", label: "Hostinger Email" },
  { value: "custom", label: "Custom SMTP" }
];

const PROVIDER_HOST_HINTS: Record<string, string> = {
  gmail: "smtp.gmail.com",
  outlook: "smtp.office365.com",
  yahoo: "smtp.mail.yahoo.com",
  hostinger: "smtp.hostinger.com",
  custom: "Enter your SMTP host"
};

const emptyForm = {
  name: "",
  email: "",
  territory: "",
  property_type: "",
  email_provider: "gmail",
  email_username: "",
  email_password: "",
  smtp_host: "",
  smtp_port: 587,
  smtp_use_tls: true,
  email_account_active: true
};

export default function AgentsPage() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [form, setForm] = useState(emptyForm);
  const [modalOpen, setModalOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function load() {
    setLoading(true);
    try {
      setAgents(await apiGet<Agent[]>("/agents/list"));
      setError("");
    } catch {
      setAgents([]);
      setError("Could not load agents. Check that the backend is running.");
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
      await apiPost("/agents", { ...form, active: true });
      setForm(emptyForm);
      setModalOpen(false);
      setNotice("Agent added successfully.");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Agent creation failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <PageHeader
        action={
          <Button onClick={() => setModalOpen(true)} startIcon={<AddOutlinedIcon />} variant="contained">
            Add Agent
          </Button>
        }
        description="Manage advisors by territory, specialization, and sender mailbox configuration."
        eyebrow="Agents"
        title="Assignment team"
      />

      <PanelCard
        action={
          <Button onClick={() => setModalOpen(true)} startIcon={<GroupAddOutlinedIcon />} variant="outlined">
            Add Agent
          </Button>
        }
        description={`${agents.length} advisors available for assignment. Scroll horizontally to view mailbox columns.`}
        icon={<GroupsOutlinedIcon color="primary" />}
        title="Active agents"
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
        ) : agents.length ? (
          <TableContainer
            sx={{
              border: "1px solid",
              borderColor: "divider",
              borderRadius: 2,
              maxWidth: "100%",
              overflowX: "auto",
              WebkitOverflowScrolling: "touch"
            }}
          >
            <Table size="small" sx={{ minWidth: 980, tableLayout: "fixed" }}>
              <TableHead>
                <TableRow>
                  <TableCell sx={{ width: 190 }}>Name</TableCell>
                  <TableCell sx={{ width: 260 }}>Email</TableCell>
                  <TableCell sx={{ width: 210 }}>Provider</TableCell>
                  <TableCell sx={{ width: 150 }}>Territory</TableCell>
                  <TableCell sx={{ width: 170 }}>Specialization</TableCell>
                  <TableCell sx={{ width: 160 }}>Status</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {agents.map((agent) => (
                  <TableRow hover key={agent.id}>
                    <TableCell>
                      <Typography sx={{ fontWeight: 850 }}>{agent.name}</Typography>
                    </TableCell>
                    <TableCell>
                      <Stack spacing={0.35}>
                        <Typography sx={{ overflowWrap: "anywhere" }}>{agent.email}</Typography>
                        <Typography color="text.secondary" sx={{ overflowWrap: "anywhere" }} variant="caption">
                          Sender: {agent.email_username || agent.email}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <Chip label={providerLabel(agent.email_provider)} size="small" sx={{ fontWeight: 850 }} />
                    </TableCell>
                    <TableCell>{agent.territory || "Any"}</TableCell>
                    <TableCell>{agent.property_type || "Any"}</TableCell>
                    <TableCell>
                      <Chip
                        color={agent.email_account_active ? "success" : "default"}
                        label={agent.email_account_active ? "Mailbox Active" : "Mailbox Inactive"}
                        size="small"
                        variant="outlined"
                      />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <EmptyState title="No agents configured" description="Add an advisor to start assigning hot leads automatically." />
        )}
      </PanelCard>

      <Dialog fullWidth maxWidth="md" onClose={closeModal} open={modalOpen}>
        <Box component="form" onSubmit={submit}>
          <DialogTitle sx={{ pb: 1 }}>
            <Stack spacing={0.5}>
              <Typography component="span" sx={{ fontSize: 20, fontWeight: 900 }}>
                Add Agent
              </Typography>
              <Typography color="text.secondary" variant="body2">
                Add assignment details and the mailbox used for initial and follow-up lead emails.
              </Typography>
            </Stack>
          </DialogTitle>
          <DialogContent dividers>
            <Stack spacing={1.5} sx={{ pt: 0.5 }}>
              <Box sx={{ display: "grid", gap: 1.5, gridTemplateColumns: { xs: "1fr", sm: "1fr 1fr" } }}>
                <TextField label="Name" required value={form.name} onChange={(event) => setForm({ ...form, name: event.target.value })} />
                <TextField
                  label="Email"
                  required
                  type="email"
                  value={form.email}
                  onChange={(event) => setForm({ ...form, email: event.target.value })}
                />
                <TextField label="Territory" value={form.territory} onChange={(event) => setForm({ ...form, territory: event.target.value })} />
                <TextField
                  label="Property type"
                  value={form.property_type}
                  onChange={(event) => setForm({ ...form, property_type: event.target.value })}
                />
                <TextField
                  label="Email provider"
                  select
                  value={form.email_provider}
                  onChange={(event) => setForm({ ...form, email_provider: event.target.value })}
                >
                  {EMAIL_PROVIDERS.map((provider) => (
                    <MenuItem key={provider.value} value={provider.value}>
                      {provider.label}
                    </MenuItem>
                  ))}
                </TextField>
                <TextField
                  helperText="Usually same as agent email."
                  label="Sender email / username"
                  type="email"
                  value={form.email_username}
                  onChange={(event) => setForm({ ...form, email_username: event.target.value })}
                />
                <TextField
                  helperText="Use app password for Gmail, Outlook, Yahoo, or Hostinger."
                  label="App password"
                  type="password"
                  value={form.email_password}
                  onChange={(event) => setForm({ ...form, email_password: event.target.value })}
                />
                <TextField
                  helperText={`Default: ${PROVIDER_HOST_HINTS[form.email_provider]}`}
                  label="SMTP host"
                  value={form.smtp_host}
                  onChange={(event) => setForm({ ...form, smtp_host: event.target.value })}
                />
                <TextField
                  label="SMTP port"
                  type="number"
                  value={form.smtp_port}
                  onChange={(event) => setForm({ ...form, smtp_port: Number(event.target.value) || 587 })}
                />
              </Box>
              <Stack spacing={0.5}>
                <FormControlLabel
                  control={<Checkbox checked={form.smtp_use_tls} onChange={(event) => setForm({ ...form, smtp_use_tls: event.target.checked })} />}
                  label="Use TLS for SMTP"
                />
                <FormControlLabel
                  control={
                    <Checkbox
                      checked={form.email_account_active}
                      onChange={(event) => setForm({ ...form, email_account_active: event.target.checked })}
                    />
                  }
                  label="Mailbox active for lead emails"
                />
              </Stack>
              {error && modalOpen ? <Alert severity="error">{error}</Alert> : null}
            </Stack>
          </DialogContent>
          <DialogActions sx={{ px: 3, py: 2 }}>
            <Button disabled={submitting} onClick={closeModal} variant="outlined">
              Cancel
            </Button>
            <Button disabled={submitting || !form.name || !form.email} startIcon={<GroupAddOutlinedIcon />} type="submit" variant="contained">
              {submitting ? "Saving..." : "Save Agent"}
            </Button>
          </DialogActions>
        </Box>
      </Dialog>
    </>
  );
}

function providerLabel(value?: string) {
  return EMAIL_PROVIDERS.find((provider) => provider.value === value)?.label || "Custom SMTP";
}

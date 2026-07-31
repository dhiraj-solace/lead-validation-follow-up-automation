import { apiGet, Lead } from "@/lib/api";
import Link from "next/link";
import CalendarMonthOutlinedIcon from "@mui/icons-material/CalendarMonthOutlined";
import {
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";
import { EmptyState, PageHeader, PanelCard, ScoreChip } from "../ui";

export default async function FollowupsPage() {
  const queue = await apiGet<Lead[]>("/followups/queue").catch(() => []);

  return (
    <>
      <PageHeader
        description="Track leads that are waiting for the next scheduled email or agent action."
        eyebrow="Follow-ups"
        title="Active outreach queue"
      />

      <PanelCard
        description={`${queue.length} leads have pending outreach activity.`}
        icon={<CalendarMonthOutlinedIcon color="primary" />}
        title="Queued follow-ups"
      >
        {queue.length ? (
          <TableContainer sx={{ border: "1px solid", borderColor: "divider", borderRadius: 2 }}>
            <Table sx={{ minWidth: 820 }}>
              <TableHead>
                <TableRow>
                  <TableCell>Lead</TableCell>
                  <TableCell>Category</TableCell>
                  <TableCell>Step</TableCell>
                  <TableCell>Next Follow-up</TableCell>
                  <TableCell>Agent</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {queue.map((lead) => (
                  <TableRow hover key={lead.id}>
                    <TableCell>
                      <Stack spacing={0.35}>
                        <Link href={`/leads/${lead.id}`}>
                          <Typography component="span" sx={{ fontWeight: 850 }}>
                            {lead.name}
                          </Typography>
                        </Link>
                        <Typography color="text.secondary" variant="body2">
                          {lead.email || "-"}
                        </Typography>
                      </Stack>
                    </TableCell>
                    <TableCell>
                      <ScoreChip band={lead.score_band} />
                    </TableCell>
                    <TableCell>{lead.followup_step || 0}</TableCell>
                    <TableCell>{lead.next_followup_at || "-"}</TableCell>
                    <TableCell>{lead.assigned_agent_name || "Unassigned"}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        ) : (
          <EmptyState
            title="No active follow-ups"
            description="Leads enter this queue after drafts are sent or nurture activity is scheduled."
          />
        )}
      </PanelCard>
    </>
  );
}

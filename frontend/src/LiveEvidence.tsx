import {
  Button,
  Dialog,
  DialogSurface,
  DialogTitle,
  DialogBody,
  DialogContent,
  DialogActions,
  DialogTrigger,
} from "@fluentui/react-components";
import {
  clientFacts,
  type ClientView,
  type DemoViewModel,
} from "./live-contracts";

export function EvidenceButton({
  id,
  model,
  client,
}: {
  id: string;
  model: DemoViewModel;
  client: ClientView;
}) {
  const fact = clientFacts(client).find((item) => item.id === id);
  const evidence = model.evidence?.[id] ?? model.connected_evidence?.[id];
  const memory = client.memory_tab?.find(
    (item) => item.id === id || item.evidence_id === id,
  );
  return (
    <Dialog>
      <DialogTrigger disableButtonEnhancement>
        <Button size="small" appearance="subtle">
          Evidence: {id}
        </Button>
      </DialogTrigger>
      <DialogSurface className="live-evidence">
        <DialogBody>
          <DialogTitle>Exact Evidence</DialogTitle>
          <DialogContent>
            <p className="live-id">{id}</p>
            {fact ? (
              <>
                <p>
                  Deterministic Fact, including formula, inputs and As-of Date.
                </p>
                <pre>{JSON.stringify(fact, null, 2)}</pre>
                {fact.evidence_ids?.map((sourceId) => (
                  <EvidenceButton
                    key={sourceId}
                    id={sourceId}
                    model={model}
                    client={client}
                  />
                ))}
              </>
            ) : evidence || memory ? (
              <pre>{JSON.stringify(evidence ?? memory, null, 2)}</pre>
            ) : (
              <p>
                This reference is not available in the current Demo View Model.
                No substitute source is shown.
              </p>
            )}
          </DialogContent>
          <DialogActions>
            <DialogTrigger disableButtonEnhancement>
              <Button appearance="primary">Close</Button>
            </DialogTrigger>
          </DialogActions>
        </DialogBody>
      </DialogSurface>
    </Dialog>
  );
}

import { bound } from "@goauthentik/elements/decorators/bound.js";

import { LitElement, ReactiveController, ReactiveControllerHost } from "lit";

type ReactiveElementHost = Partial<ReactiveControllerHost> & LitElement;

type ModalElement = LitElement & { closeModal(): void };

export class ModalShowEvent extends Event {
    modal: ModalElement;
    constructor(modal: ModalElement) {
        super("ak-modal-show", { bubbles: true, composed: true });
        this.modal = modal;
    }
}

export class ModalHideEvent extends Event {
    modal: ModalElement;
    constructor(modal: ModalElement) {
        super("ak-modal-hide", { bubbles: true, composed: true });
        this.modal = modal;
    }
}

declare global {
    interface GlobalEventHandlersEventMap {
        "ak-modal-show": ModalShowEvent;
        "ak-modal-hide": ModalHideEvent;
    }
}

const modalIsLive = (modal: ModalElement) => modal.isConnected && modal.checkVisibility();

/**
 * class ModalOrchetrationController
 *
 * A top-level controller that listens for requests from modals to be added to
 * the management list, such that the *topmost* modal will be closed (and all
 * references to it eliminated) whenever the user presses the Escape key.
 * Can also take ModalHideEvent requests and automatically close the modal
 * sending the event.
 */


export class ModalOrchestrationController implements ReactiveController {
    host!: ReactiveElementHost;

    knownModals: ModalElement[] = [];

    constructor(host: ReactiveElementHost) {
        this.host = host;
        host.addController(this);
    }

    hostConnected() {
        window.addEventListener("keyup", this.handleKeyup);
        window.addEventListener("ak-modal-show", this.addModal);
        window.addEventListener("ak-modal-hide", this.closeModal);
    }

    hostDisconnected() {
        window.removeEventListener("keyup", this.handleKeyup);
        window.removeEventListener("ak-modal-show", this.addModal);
        window.removeEventListener("ak-modal-hide", this.closeModal);
    }

    @bound
    addModal(e: ModalShowEvent) {
        this.knownModals = [...this.knownModals, e.modal];
    }

    scheduleCleanup(modal: ModalElement) {
        setTimeout(() => {
            this.knownModals = this.knownModals.filter((m) => modalIsLive(m) && modal !== m);
        }, 0);
    }

    @bound
    closeModal(e: ModalHideEvent) {
        const modal = e.modal;
        if (!modalIsLive(modal)) {
            return;
        }
        modal.closeModal();
        this.scheduleCleanup(modal);
    }

    removeTopmostModal() {
        while (true) {
            const modal = this.knownModals.pop();
            if (!modal) {
                break;
            }
            if (!modalIsLive(modal)) {
                continue;
            }

            modal.closeModal();
            this.scheduleCleanup(modal);
            break;
        }
    }

    @bound
    handleKeyup(e: KeyboardEvent) {
        // The latter handles Firefox 37 and earlier.
        if (e.key === "Escape" || e.key === "Esc") {
            this.removeTopmostModal();
        }
    }
}

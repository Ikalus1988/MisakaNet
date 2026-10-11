import { ProfileManager } from '../profile-manager';

export class MarketplaceManager {
    private profileManager: ProfileManager;

    constructor(profileManager: ProfileManager) {
        this.profileManager = profileManager;
    }

    /**
     * Realiza uma operação de instalação/atualização no marketplace.
     * Corrigido para não dropar bundles existentes no profile que não foram instalados via GUI.
     */
    async performMarketplaceOperation(operation: 'install' | 'update', bundleId: string) {
        // 1. Executa a operação de instalação/update padrão
        await this.executeOperation(operation, bundleId);

        // 2. Recupera o estado atual do perfil (incluindo bundles manuais)
        const currentProfile = await this.profileManager.getProfile();
        const existingBundles = currentProfile.bundles || [];

        // 3. Obtém o registro do que o marketplace gerencia
        const marketManagedBundles = await this.getMarketRecord();

        // 4. Merge: Mantém bundles existentes + bundles do mercado
        // Usamos um Set para garantir unicidade baseada no ID do bundle
        const mergedBundles = [...existingBundles];
        
        for (const marketBundle of marketManagedBundles) {
            if (!mergedBundles.some(b => b.id === marketBundle.id)) {
                mergedBundles.push(marketBundle);
            }
        }

        // 5. Atualiza o perfil com a lista consolidada
        await this.profileManager.updateProfile({
            ...currentProfile,
            bundles: mergedBundles
        });

        console.log(`[Marketplace] Profile synchronized. Total bundles: ${mergedBundles.length}`);
    }

    private async executeOperation(operation: string, bundleId: string) {
        // Lógica original de instalação/update...
    }

    private async getMarketRecord(): Promise<any[]> {
        // Lógica que retorna apenas o que o marketplace rastreia...
        return []; 
    }
}

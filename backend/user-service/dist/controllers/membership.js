"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
const database_1 = require("../config/database");
class MembershipController {
    static async getPlans(req, res) {
        const plans = await database_1.prisma.membershipPlan.findMany({
            where: { isActive: true },
            orderBy: [
                { level: 'asc' },
                { durationMonths: 'asc' },
            ],
        });
        const formattedPlans = plans.map(plan => ({
            id: plan.id,
            name: plan.name,
            level: plan.level.toLowerCase(),
            duration_months: plan.durationMonths,
            price: plan.price.toString(),
            original_price: plan.originalPrice?.toString(),
            discount: plan.discount,
            features: plan.features,
            is_active: plan.isActive,
            popular: plan.popular,
        }));
        res.json({
            success: true,
            code: 200,
            message: '获取成功',
            data: formattedPlans,
            timestamp: new Date().toISOString(),
            request_id: req.headers['x-request-id'],
        });
    }
}
exports.default = MembershipController;
//# sourceMappingURL=membership.js.map